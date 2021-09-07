#!/usr/bin/python
# -*- coding: utf-8 -*-
import os, re
from socket import *
import json
import struct
import protobuf_converter as pc

majorVersion = 0
minorVersion = 1
patchVersion = 0
serverIp = "127.0.0.1"
serverPort = 5200
Timeout = 5

PACK_HEADER = '>HBBHHL'
#client_socket = socket(AF_INET, SOCK_STREAM)

def request_sender(request, outputPath):

    # create response file, if already exist, delete it
    fileHandle = open(request, 'r')
    requestFileName = os.path.basename(request)
    responseFile = outputPath + '/' + re.sub('args', 'resp', requestFileName)
    if os.path.exists(responseFile):
        os.remove(responseFile)
    respHandle = open(responseFile, 'w')
    respHandle.write('[\n')
    # go through all the request in request file
    reqDict = json.load(fileHandle)
    for i in range(len(reqDict)):
        allReq = reqDict[i]['step']
        respHandle.write('\t{\n')
        for j in range(len(allReq)):
            # prepare request data
            seqNum = reqDict[i][allReq[j]]['seqNum']
            reqType = int(allReq[j], 16)
            #packedData = struct.pack(PACK_HEADER, 0, seqNum, reqType, 0, 0)
            protoData = pc.getParamProto(reqType, reqDict[i][allReq[j]])
            packedData = struct.pack(PACK_HEADER, 0, seqNum, reqType, 0, 0, 12 + len(protoData))
            packedData = packedData + protoData

            client_socket = socket(AF_INET, SOCK_STREAM)
            client_socket.connect((serverIp, serverPort))
            client_socket.settimeout(Timeout)
            # send TCP request
            client_socket.send(packedData)

            response_handler(client_socket, reqType, seqNum, respHandle)

            # close tcp socket
            client_socket.close()

            # one request finished
            tail = "\n"
            if j != len(allReq) - 1:
                tail = ",\n"
            respHandle.write(tail)

        # one rounad of request finished
        tail = '\t}\n'
        if i != len(reqDict) - 1:
            tail = '\t},\n'
        respHandle.write(tail)

    # done with response file written
    respHandle.write(']')
    respHandle.close()

def response_handler(client_socket, reqType, reqSeqNum, respHandle):
    retCode = 0
    exit_flg = 0
    recv_data = ''
    recved_len = 0
    while exit_flg != 1:
        try:
            retCode, data = 0, client_socket.recv(204800)
            recved_len += len(data)
            if data:
                recv_data += data
            else:
                exit_flg = 1
        except Exception, e:
            retCode, recv_data = 2, ""
            exit_flg = 1
    if retCode == 0:
        reserved, rspSeqNum, rspType, minVersion, majVersion, frameLen = struct.unpack(PACK_HEADER, recv_data[0:12])
        if frameLen != len(recv_data):
            print("frame length error: {}-{}".format(frameLen, len(recv_data)))
            None
        if rspSeqNum != reqSeqNum:
            None
        else:
            respStr, respDict = pc.getRespDict(reqType, rspType, rspSeqNum, recv_data[12:len(recv_data)])
    else:
            # 0xFFFF stands for timeout here
            respStr, respDict = pc.getRespDict(reqType, 0xFFFF, 0, "")

    respHandle.write(respStr)


if __name__ == "__main__":
    # cs service request file path
    request = ''
    # cs service response file path
    output = ''
    request_sender(request, output)
