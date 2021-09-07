#!/usr/bin/python
# -*- coding: utf-8 -*-

import message_pb2
import json
import os
import sys
import struct
import udp_handler
import protobuf_converter as pc
import re
import time
from optparse import OptionParser
import call_dapi_client
import dapiPythonCppInterface as dapiCppIntf

majorVersion = 0
minorVersion = 1
patchVersion = 0
udpSocket = None
serverIp = "127.0.0.1"
serverPort = 5200
Timeout = 5

PACK_HEADER = '>HBBHHL'

udpSocket = udp_handler.UdpSocket(serverIp, serverPort, Timeout)


def request_sender(request, outputPath):
    global udpSocket

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
            protoData = pc.getParamProto(reqType, reqDict[i][allReq[j]])
            packedData = struct.pack(PACK_HEADER, 0, seqNum, reqType, 0, 0,
                                     12 + len(protoData))
            packedData = packedData + protoData

            # send request
            udpSocket.send_data(packedData)

            # for test
            # testInterface(reqType, seqNum, packedData, respHandle)

            # handle response
            response_handler(reqType, seqNum, respHandle)

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

    respHandle.write(']')
    respHandle.close()


def testInterface(reqType, reqSeqNum, frameData, respHandle):
    # reserved, rspSeqNum, rspType, minVersion, majVersion = struct.unpack(
    #             PACK_HEADER, data[0:8])

    resp = message_pb2.PTHorizonBuildResp()
    resp.errCode = 0
    resp.horizonInfo.length = 222
    resp.horizonInfo.rootPathID = 0
    allpath = resp.horizonInfo.allPaths.add()
    allpath.id = 9
    allpath.parentPathID = 1
    allpath.offsetFromParentPath = 91
    allpath.offsetFromRoot = 92
    allpath.length = 94

    respStr, respDict = pc.getRespDict(reqType, reqType, reqSeqNum,
                              resp.SerializeToString())

    print "----"
    print respStr
    print "----"

    respHandle.write(respStr)


def response_handler(reqType, reqSeqNum, respHandle):
    global udpSocket

    retCode = 0
    exit_flg = 0
    while exit_flg != 1:
        retCode, data, addressFrom = udpSocket.receive_data()
        if retCode == 0:
            reserved, rspSeqNum, rspType, minVersion, majVersion, frameLen = struct.unpack(
                PACK_HEADER, data[0:12])
            # if rspSeqNum != reqSeqNum or frameLen != len(data):
            if frameLen != len(data):
                print("frame length error: {}-{}".format(frameLen, len(data)))
                continue
            if rspSeqNum != reqSeqNum:
                continue
            else:
                respStr, respDict = pc.getRespDict(reqType, rspType, rspSeqNum,
                                          data[12:len(data)])
                exit_flg = 1
        else:
            # 0xFFFF stands for timeout here
            respStr, respDict = pc.getRespDict(reqType, 0xFFFF, 0, "")
            exit_flg = 1

    respHandle.write(respStr)


def updateSocketInfo(options):
    global udpSocket
    global serverIp
    global serverPort
    global Timeout

    serverIp = options.ip
    serverPort = options.port
    udpSocket = udp_handler.UdpSocket(serverIp, serverPort, Timeout)


def getRequestId(id):
    return id


def parseParameters(options):
    paramDict = {}

    if "0xF0" == options.interface:
        paramList = options.parameters.split(",")
        if 3 == len(paramList):
            ndsPoint = {}
            ndsPoint['longitude'] = int(paramList[0])
            ndsPoint['latitude'] = int(paramList[1])
            ndsPoint['altitude'] = int(paramList[2])
            paramDict['NDSPoint'] = ndsPoint
    elif "0xF1" == options.interface:
        paramDict['laneID'] = getRequestId(options.parameters)
    elif "0xF2" == options.interface:
        paramDict['lineID'] = getRequestId(options.parameters)
    elif "0xF3" == options.interface:
        paramDict['curveID'] = getRequestId(options.parameters)
    elif "0xF4" == options.interface:
        paramDict['landscapeID'] = getRequestId(options.parameters)
    elif "0xF5" == options.interface:
        paramDict['evpID'] = getRequestId(options.parameters)
    else:
        pass

    return paramDict


def request_parameter_sender(options):
    global udpSocket
    seqNum = options.sequenceNum
    reqType = int(options.interface, 16)
    packedData = struct.pack(PACK_HEADER, 0, seqNum, reqType, 0, 0)

    paramDict = parseParameters(options)
    if None == paramDict:
        if paramDict is None:
            print("parameters error")
            return

    protoData = pc.getParamProto(reqType, paramDict)
    packedData = packedData + protoData
    udpSocket.send_data(packedData)

    response_message_handler(reqType, seqNum)


def response_message_handler(reqType, reqSeqNum):
    retCode = 0
    exit_flg = 0
    while exit_flg != 1:
        retCode, data, addressFrom = udpSocket.receive_data()
        if retCode == 0:
            reserved, rspSeqNum, rspType, minVersion, majVersion = struct.unpack(
                PACK_HEADER, data[0:8])
            if rspSeqNum != reqSeqNum:
                continue
            else:
                respStr, respDict = pc.getRespDict(reqType, rspType, rspSeqNum,
                                          data[8:len(data)])
                exit_flg = 1

                print "[\n{"
                print str(respStr)
                print "\n}\n]"
        else:
            # 0xFFFF stands for timeout here
            respStr, respDict = pc.getRespDict(reqType, 0xFFFF, 0, "")
            exit_flg = 1

            print "\nRequest Timeout\n"
            print "Please check:"
            print "             1. the server state"
            print "             2. the server ip"
            print "             3. the server port"
            print ""


def usageInfo():
    print("%s %d.%d.%d" % (__file__, majorVersion, minorVersion, patchVersion))
    print("\nOptions:")
    print("    -t Interface Type")
    print("        0xF0: Get Lane by Positon")
    print("        0xF1: Get Lane by ID")
    print("        0xF2: Get Line by ID")
    print("        0xF3: Get Nurbscurve by ID")
    print("        0xF4: Get Landscape by ID")
    print("    -p Parameters:")
    print("        For 0xF0: \"Longitude, Latitude, Altitude\"")
    print("        For 0xF1: \"Lane ID\"")
    print("        For 0xF2: \"Line ID\"")
    print("        For 0xF3: \"Curve ID\"")
    print("        For 0xF4: \"Landscape ID\"")
    print("        For 0xF5: \"EVP ID\"")
    print("    -a Server IP address, the default value is 127.0.0.1")
    print("    -P Server Port, the default value is 5200")
    print("\nExample:")
    print(
        "    %s -t 0xF1 -p \"1_2_3\" --> Send request of GetLaneByID to Server(ip: 127.0.0.1, port: 5200)"
        % __file__)
    print(
        "    %s -t 0xF1 -p \"12345\" -d --> Send request of GetLaneByID to Server(ip: 127.0.0.1, port: 5200)"
        % __file__)
    print("")


if __name__ == "__main__":
    parser = OptionParser(usage="%prog [options] ...")
    parser.add_option("-t",
                      action="store",
                      dest="interface",
                      metavar="type",
                      help="Interface Type:\
                                                                                           0xF0: Get Lane by Positon\
                                                                                           0xF1: Get Lane by ID\
                                                                                           0xF2: Get Line by ID\
                                                                                           0xF3: Get Nurbscurve by ID\
                                                                                           0xF4: Get Landscape by ID\
                                                                                           0xF5: Get EVP by ID"
                      )
    parser.add_option("-p",
                      action="store",
                      dest="parameters",
                      metavar="parameters",
                      help="Parameters: \
                                                                                            For 0xF0: \"Latitude, Longitude, Altitude\"\
                                                                                            For 0xF1: \"Lane ID\"\
                                                                                            For 0xF2: \"Line ID\"\
                                                                                            For 0xF3: \"Curve ID\"\
                                                                                            For 0xF4: \"Landscape ID\"\
                                                                                            For 0xF5: \"EVP ID\""
                      )
    parser.add_option("-s",
                      action="store",
                      dest="sequenceNum",
                      default=1,
                      type="int",
                      metavar="sequence number",
                      help="Sequence Number, the default value is 1")
    parser.add_option(
        "-a",
        action="store",
        dest="ip",
        default="127.0.0.1",
        metavar="ip",
        help="Server IP address, the default value is \"127.0.0.1\"")
    parser.add_option("-P",
                      action="store",
                      dest="port",
                      default=5200,
                      type="int",
                      metavar="port",
                      help="Server IP address, the default value is 5200")
    (options, args) = parser.parse_args()

    if 1 == len(sys.argv):
        usageInfo()
        sys.exit(-1)

    updateSocketInfo(options)
    request_parameter_sender(options)
