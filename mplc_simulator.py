import pymcprotocol
import socket
import time
import requests
import json
import random

sc_ip = ""
sc_port = ""
api_token_type = None
api_access_token = None

c_1 = 11702
c_2 = 11704
c_3 = 11705
c_4 = 11707

# EQ
c_18 = 18
c_19 = 19
c_20 = 20
c_21 = 21

# CV
# ONLY PUT
c_25 = 25
c_27 = 27

# ONLY GET
c_24 = 24
c_26 = 26

task_dict = {
    "0": [c_1, c_20], "1": [c_2, c_25], "2": [c_3, c_21], "3": [c_4, c_27],
    "4": [c_20, c_1], "5": [c_26, c_2], "6": [c_21, c_3], "7": [c_24, c_4],
    "8": [c_1, c_18], "9": [c_2, c_25], "10": [c_3, c_19], "11": [c_4, c_27],
    "12": [c_18, c_1], "13": [c_26, c_2], "14": [c_19, c_3], "15": [c_24, c_4]
}

def apiGetToken():
    global sc_ip
    global sc_port
    global api_token_type
    global api_access_token

    login_heder = {'accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                }
    get_token_url = f"http://{sc_ip}:{sc_port}/login/access-token"
    r = requests.post(url=get_token_url, headers=login_heder,
                    data=f"username=&password=")

    isLoginOK = False

    if int(r.status_code) == 200:
        response_txt = json.loads(r.text)
        api_token_type = response_txt["token_type"]
        api_access_token = response_txt["access_token"]
        isLoginOK = True
    else:
        api_token_type = None
        api_access_token = None
        
    return isLoginOK

def apiGetWMSCellStatus(cell_id):
        global sc_ip
        global sc_port
        global api_token_type
        global api_access_token

        if api_access_token == None:
            apiGetToken()
        else:
            pass

        reset_headers = {'accept': 'application/json',
                        'Content-Type': 'application/json',
                        'Authorization': f'{api_token_type} {api_access_token}'}

        r = requests.get(url=f"http://{sc_ip}:{sc_port}/v2/wms?cell_id={cell_id}&mode=load_only", headers=reset_headers)
        
        isResetOK = False

        if int(r.status_code) == 200:
            isResetOK = True
        else:
            pass

        return isResetOK, r.text

def checkSCWMSStatus(from_cell_id, to_cell_id):
        try:
            from_cell_id_resetStatus, from_cell_id_resetResponse = apiGetWMSCellStatus(from_cell_id)
        
            if from_cell_id_resetStatus == False:
                raise Exception(f" === checkSCWMSStatus from_cell_id: {from_cell_id} Error : {from_cell_id_resetResponse}. it will try it again! ==== ")
            
            to_cell_id_resetStatus, to_cell_id_resetResponse = apiGetWMSCellStatus(to_cell_id)
        
            if to_cell_id_resetStatus == False:
                raise Exception(f" === checkSCWMSStatus to_cell_id: {to_cell_id} Error : {to_cell_id_resetResponse}. it will try it again! ==== ")

            from_load = json.loads(from_cell_id_resetResponse)["cells"][0]["load"]
            to_load = json.loads(to_cell_id_resetResponse)["cells"][0]["load"]

            can_send_task = False

            if from_load == "rack" and to_load == "empty":
                can_send_task = True

            print(f"Cell load from_cell_id: {from_load}, to_cell_id: {to_load}, can send task? {can_send_task}")

            return can_send_task
                
        except Exception as e:
            print(f"{e}")
            apiGetToken()
            checkSCWMSStatus(from_cell_id, to_cell_id)
            print(f"  === Update updateWMSState Fail it will retry! ==== ")


def sendFakeTask(mplc, robot_mplc_read, from_cell, to_cell):
    read_start_addr = int(robot_mplc_read[1::])
    excute_from_to_addr = f"D0{read_start_addr+1}"
    carrier_id_addr = f"D0{read_start_addr+5}"

    # print(read_start_addr, excute_from_to_addr, carrier_id_addr, from_cell, to_cell)

    write_plc_response = mplc.batchwrite_wordunits(headdevice=excute_from_to_addr, values=[256, from_cell, to_cell])
    write_plc_response = mplc.batchwrite_wordunits(headdevice=carrier_id_addr, values=genCarrierID())

def genCarrierID():
    random_s = 10000
    random_e = 20000

    return [random.randint(random_s, random_e), random.randint(random_s, random_e), random.randint(random_s, random_e)]

def genRobotExcutingTaskDict(robot_dict):
    tmp_dict = {}
    for robot_id, robot_mplc_setting in robot_dict.items():
        tmp_dict[robot_id] = None
    return tmp_dict

def isOpen(ip, port):
   s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   try:
      s.connect((ip, int(port)))
      s.shutdown(2)
      return True
   except:
      return False

def resetMPLCRead(mplc, robot_mplc_read):
    read_start_addr = int(robot_mplc_read[1::])
    excute_from_to_addr = f"D0{read_start_addr+1}"
    carrier_id_addr = f"D0{read_start_addr+5}"

    # print(read_start_addr, excute_from_to_addr, carrier_id_addr)
    write_plc_response = mplc.batchwrite_wordunits(headdevice=excute_from_to_addr, values=[0, 0, 0])
    write_plc_response = mplc.batchwrite_wordunits(headdevice=carrier_id_addr, values=[0, 0, 0])

def readMPLC(mplc_ip_port, mplc, robot_dict, send_task):
    mode = "Read only"
    if send_task:
        mode = "Sim"
        excuting_task_dict = genRobotExcutingTaskDict(robot_dict)
        task_index = 0
        global task_dict
        total_round = 0
    try:
        while True:
            print(f'\n')
            print(f'================================== START mode: {mode} ============================================')
            if send_task:
                print(f'Current Excuting Flow: {excuting_task_dict}, Total Round: {total_round}')

            for robot_id, robot in robot_dict.items():
                read_plc_response1 = mplc.batchread_wordunits(headdevice=robot[0], readsize=10)
                read_plc_response2 = mplc.batchread_wordunits(headdevice=robot[1], readsize=30)
                
                print(f'{robot_id} Read: {read_plc_response1}')
                print(f'{robot_id} Write: {read_plc_response2}')

                if send_task and all(v == 0 for v in read_plc_response1):
                    task = task_dict[f"{task_index}"]
                    from_cell = task[0]
                    to_cell = task[1]

                    is_finish = read_plc_response2[0]

                    if is_finish == 11:
                        print(f"----- {robot_id} Try Select Task {task_index}, From: {from_cell}, To: {to_cell} -----")

                        excuting_task_dict[robot_id] = None

                        if task_index in excuting_task_dict.values():
                            task_index += 1
                            print(f"----- {robot_id} Select Task Already been choose send next task -----")
                        else:
                            can_send_task = checkSCWMSStatus(f"{from_cell}", f"{to_cell}")

                            if can_send_task:
                                print(f"----- {robot_id} Select Task Send {task_index}, From: {from_cell}, To: {to_cell} -----") 
                                sendFakeTask(mplc, robot[0], from_cell, to_cell)
                                excuting_task_dict[robot_id] = task_index
                                task_index += 1
                                time.sleep(3)
                    else:
                        pass

                    
                    if (task_index == len(task_dict.keys())):
                        task_index = 0
                        total_round += 1
                    # else:
                    #     task_index += 1
            
            read_plc_response3 = mplc.batchread_wordunits(headdevice='D0425', readsize=3)
            read_plc_response4 = mplc.batchread_wordunits(headdevice='D0541', readsize=60)
            read_plc_response5 = mplc.batchread_wordunits(headdevice='D0422', readsize=3)
            read_plc_response6 = mplc.batchread_wordunits(headdevice='D0601', readsize=60)

            eq_busy_01 = read_plc_response3[(425-425)]
            eq_busy_02 = read_plc_response3[(426-425)]
            eq_busy_03 = read_plc_response3[(427-425)]
            print(f'EQ: busy_01: {eq_busy_01}, busy_02: {eq_busy_02}, busy_03: {eq_busy_03}')
            cv_busy_01 = read_plc_response4[(543-541)]
            cv_busy_02 = read_plc_response4[(573-541)]
            cv_carrier_id = read_plc_response4[(30+21):(30+21+3)]
            print(f'CV: busy_DO4: {cv_busy_01}, busy_DO5: {cv_busy_02}, br_code: {cv_carrier_id}')

            eq2_busy_01 = read_plc_response5[(422-422)]
            eq2_busy_02 = read_plc_response5[(423-422)]
            eq2_busy_03 = read_plc_response5[(424-422)]
            print(f'EQ2: busy_01: {eq2_busy_01}, busy_02: {eq2_busy_02}, busy_03: {eq2_busy_03}')
            cv2_busy_01 = read_plc_response6[(603-601)]
            cv2_busy_02 = read_plc_response6[(633-601)]
            cv2_carrier_id = read_plc_response6[(30+21):(30+21+3)]
            print(f'CV2: busy_DO4: {cv2_busy_01}, busy_DO5: {cv2_busy_02}, br_code: {cv2_carrier_id}')

            # print(f'Next Task id will be : {task_index}')
            print(f'================================== END ============================================')
            time.sleep(1)
    except Exception as e:
        print(e)
        while isOpen(mplc_ip_port[0], mplc_ip_port[1]) == False:
            print('Reconnceting')

        mplc.connect(mplc_ip_port[0], mplc_ip_port[1])

def sim_mplc(mplc_ip_port, robot_list, send_task=False, reset=False):
    robot_dict = {}
    
    for setting_dict in robot_list:
        for robot_id, robot_mplc_setting in setting_dict.items():
            robot_dict[robot_id] = robot_mplc_setting

    print(f"Robot Setting: {robot_dict}")


    mplc = pymcprotocol.Type3E()
    mplc.connect(mplc_ip_port[0], mplc_ip_port[1])

    if reset:
        for robot_id, robot_mplc_setting in robot_dict.items():
            read_addr = robot_mplc_setting[0]
            resetMPLCRead(mplc, read_addr)

    # Start read
    readMPLC(mplc_ip_port, mplc, robot_dict, send_task)

if __name__ == '__main__':
    print('======  Sim mplc  =======')
    mplc_ip_port = ["172.17.40.199", 2004]

    fb0 = ['D0941', 'D0841']
    fb1 = ['D0951', 'D0871']
    fb2 = ['D0471', 'D0691']
    
    robot_list = [
        {"fb0": fb0},
        {"fb1": fb1},
        {"fb2": fb2},
    ]
    
    sim_mplc(mplc_ip_port, robot_list, send_task=False, reset=False)
