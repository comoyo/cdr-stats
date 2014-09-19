#!/usr/bin/python
#
# Rerieve call information from mongoDB CDR-Stats database and generate graph output
# for web/confluence/whatever purpose
#
# Will leave a set of .png files in the directory where it's run
# Needs access to mongodb database, see mongoDBConnect() for details
# Username and password for mongodb can be found in e.g. genie configuration files
#
# import os
import sys
# import re
# time and date
import datetime
import time
# json
import json
from bson import json_util
from bson import ObjectId
# python mongo db interface
import pymongo
# graphing tool
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# db access
databasename = 'cdr-stats'
collectionname = 'cdr_common'
client = ''
db = ''
collection = []
username = ''
password = ''

# db fields
client_call_to_ringing = 'client_call_to_ringing'
trunkie_call_to_ringing = 'trunkie_call_to_ringing'
trunkie_call_to_status = 'trunkie_call_to_status'
footee_call_setup_time = 'footee_call_setup_time'
destination_number = 'destination_number'
start_uepoch = 'start_uepoch'
call_id = 'call_id'
direction = 'direction'
callee = 'callee'
caller_id_number = 'caller_id_number'
client_network_type = 'client_network_type'

# data lists
dbcalls = []

#
# Colorized output functions
# TODO! Check if output is tty, if no don't colorize
#       (like shell script "if [ -t 1 ]; then ..")
#
# textString: text string to be
def printRed(textString):
    print "%c[0;31m%s%c[0m" % (27, textString, 27)


def printGreen(textString):
    print "%c[0;32m%s%c[0m" % (27, textString, 27)


def printYellow(textString):
    print "%c[0;33m%s%c[0m" % (27, textString, 27)

#
# Establish CDR-Stats mongoDB connection
# Note! name of database is hardcoded to
#
# server: server name and port, in the form "mongodb://<hostname>:<port>"
# username: database username
# password: databae password
# verbose: set to True for debug output, False for silent operation
def mongoDBConnect(verbose, server, username, password):
    global db
    global client
    global databasename
    jsonServerInfo = ''
    jsonServerObject = ''
    if verbose:
        printYellow("*** mongo db connect and authentication ***")

    # the read_preference options compares to mongo shell's slaveOK() call,
    # we do not need to be primary
    # IF recent pymongo (ubuntu 13,14,...)
    client = pymongo.MongoClient(server, read_preference=pymongo.ReadPreference.SECONDARY, tz_aware=True)
    # ELSE old style (ubuntu12) - note this is really a Connection class, not MongoClient
    # client = pymongo.Connection(server, tz_aware=True, slave_okay=True)

    db = client[databasename]
    jsonServerInfo = client.server_info()
    jsonServerSerialized = json.dumps(jsonServerInfo, indent=2, default=json_util.default, sort_keys=True )
    jsonServerObject = json.loads(jsonServerSerialized)
    if verbose == True:
        # print jsonServerSerialized
        print "server:  " + jsonServerObject['sysInfo']
        print "version: " + jsonServerObject['version']

    result = db.authenticate(username, password)
    if result == False:
        printRed("*** authentication failure ***");
        mongoDBDisconnect()
        exit(1)
    if verbose:
        printGreen("*** authentication OK ***");
    return True

#
# Terminate CDR-Stats mongoDB connection
#
# verbose: set to True for debug output, False for silent operation
def mongoDBDisconnect(verbose):
    if client != '':
        if verbose:
            printYellow("*** connection terminated ***")
        client.disconnect()
        return True
    if verbose:
        printRed("*** no active connection ***")
    return False

#
# Retrieve CDR-Stats collections (the set of tables in the database)
#
# collectionName: name of collection/table to verify existence of
# verbose: set to True for debug output, False for silent operation
def mongoDBCollection(verbose, collectionName):
    global db
    global collection
    if verbose:
        printYellow ("*** collection ***")
    collection = db.collection_names()
    found = False;
    for c in collection:
        if verbose == True:
            print(c)
        if c.find(collectionName) != -1:
            found = True
    if found == False:
        mongoDBDisconnect()
        printRed("*** could not find " + collectionName + " in ***")
        printRed(collection)
        exit(1)
    if verbose:
        printGreen("*** OK ***")
    return True

#
# query mongo database for a set of calls within a specified time frame
#
# verbose: set to True for debug output, False for silent operation
# fromDate: start date for calls
# toDate: end date for calls
# destinationNumber: ONLY retrieve data for calls TO this destination number
# ignoreNumber: DO NOT add/count calls FROM this number
def mongoDBGetCalls(verbose, fromDate, toDate, destinationNumber, ignoreNumber):
    global db
    global ringlist
    global footeelist
    jsonResults = []
    count = 0

    if verbose:
        printYellow("*** query database for calls ***")

    if ignoreNumber == None:
        # taken from SMS+, "The +979 hack" (unassigned international number)
        ignoreNumber = "+979000000"

    # if no destination number is given, use all calls
    if destinationNumber != None:
        jsonResults = db[collectionname].find({"$and":[{"start_uepoch":{"$gte":fromDate,"$lte":toDate}},
                                                       {destination_number:destinationNumber},
                                                       {"caller_id_number":{"$ne":ignoreNumber}}]})
    else:
        jsonResults = db[collectionname].find({"$and":[{"start_uepoch":{"$gte":fromDate,"$lte":toDate}},
                                                       {"caller_id_number":{"$ne":ignoreNumber}}]})

    if verbose:
        # output number of matching calls found
        if jsonResults.count() > 0:
            printGreen("number of calls: " + str(jsonResults.count()))
        else:
            printYellow("number of calls: " + str(jsonResults.count()))

    return jsonResults

#
# Retrive single test data element for Processing
# various example queries
#
def mongoDBDataTest():
    global db

    printYellow("*** data query1 ***")
    jsonResult = db[collectionname].find_one({caller_id_number : "+4792270160"})
    printCall(jsonResult)
    # printYellow("*** data query2 ***")
    # jsonResult = db[collectionname].find_one({"client_call_quality.q_100": 2})
    # printCall(jsonResult)
    # printYellow("*** data query3 ***")
    # jsonResult = db[collectionname].find_one({"_id" : ObjectId("53ad3f6ce4b0a9b833effa65") })
    # printCall(jsonResult)

#
# output to terminal a db query result
#
# jsonResult: a single mongodb query result
def printCall(jsonResult):
    jsonSerialized = ''
    jsonObject = ''

    if not jsonResult:
        printRed("*** no data ***")
        return False
    jsonSerialized = json.dumps(jsonResult, indent=2, default=json_util.default, sort_keys=True)
    # pretty print data
    print jsonSerialized
    # jsonObject = json.loads(jsonSerialized)
    # printGreen("*** destination number:" + jsonObject[destination_number])
    return True

#
# output to terminal a list of results from a db query
#
# jsonResults: a list of mongodb query results
def printCalls(jsonResults):
    jsonSingle = ''
    jsonSerialized = ''
    jsonObject = ''

    if not jsonResults:
        printRed("*** no data ***")
        return False
    for jsonSingle in jsonResults:
        printCall(jsonSingle)
    return True

#
# Parse a set of calls, check if they are incoming from SIP-trunk and
# return a list of trunkie call to ringing times (on both 3G and WiFi)
#
# verbose: Set to True for debug output, False for silent operation
# jsonResults: List of calls from mongo db
# returns list of trunkie call to ringing values
def sipTrunkToTalkPlus(verbose, jsonResults):
    trunkieTable = []

    printYellow("*** sip trunk to talk+ client calls ***")
    for jsonSingle in jsonResults:
        isTalkPlusCaller = -1
        trunkieCallToRinging = -1
        callDirection = ''

        jsonSerialized = json.dumps(jsonSingle, indent=2, default=json_util.default, sort_keys=True)
        jsonObject = json.loads(jsonSerialized)
        if jsonObject.get(client_call_to_ringing):
            isTalkPlusCaller = jsonObject[client_call_to_ringing]
        if jsonObject.get(direction):
            callDirection = jsonObject[direction]
        # check that call is not coming from talk+
        if isTalkPlusCaller == -1 and callDirection == "inbound" and jsonObject.get(trunkie_call_to_ringing):
            trunkieCallToRinging = jsonObject[trunkie_call_to_ringing]
            trunkieTable.append(int(trunkieCallToRinging*1000))
            if verbose:
                print "trunkie INVITE to talkplus RINGING: " + str(trunkieCallToRinging)
    return trunkieTable

#
# Parse a set of calls, check if they are incoming from SIP-trunk and
# return a list of trunkie call to ringing times on TalkPlus 3G clients
#
# verbose: Set to True for debug output, False for silent operation
# jsonResults: List of calls from mongo db
# returns list of trunkie call to ringing values
def sipTrunkToTalkPlus3G(verbose, jsonResults):
    trunkieTable = []

    printYellow("*** sip trunk to talk+ 3G calls ***")
    for jsonSingle in jsonResults:
        isTalkPlusCaller = -1
        trunkieCallToRinging = -1
        callDirection = ''
        network = ''

        jsonSerialized = json.dumps(jsonSingle, indent=2, default=json_util.default, sort_keys=True)
        jsonObject = json.loads(jsonSerialized)
        if jsonObject.get(client_call_to_ringing):
            isTalkPlusCaller = jsonObject[client_call_to_ringing]
        if jsonObject.get(direction):
            callDirection = jsonObject[direction]
        jsonCallee = jsonObject.get(callee)
        if jsonCallee == None:
            continue
        if jsonCallee.get(client_network_type):
            network = jsonCallee[client_network_type]
        # check that call is not coming from talk+
        if isTalkPlusCaller == -1 and callDirection == "inbound" and network == "UNKNOWN3G" and jsonObject.get(trunkie_call_to_ringing):
            trunkieCallToRinging = jsonObject[trunkie_call_to_ringing]
            trunkieTable.append(int(trunkieCallToRinging*1000))
            if verbose:
                print "trunkie INVITE to talkplus3G RINGING: " + str(trunkieCallToRinging)
    return trunkieTable

#
# Parse a set of calls, check if they are incoming from SIP-trunk and
# return a list of trunkie call to ringing times on TalkPlus Wi-Fi clients
#
# verbose: Set to True for debug output, False for silent operation
# jsonResults: List of calls from mongo db
# returns list of trunkie call to ringing values
def sipTrunkToTalkPlusWiFi(verbose, jsonResults):
    trunkieTable = []

    printYellow("*** sip trunk to talk+ on Wi-Fi calls ***")
    for jsonSingle in jsonResults:
        trunkieCallToRinging = 0
        isTalkPlusCaller = -1
        callDirection = ''
        network = ''

        jsonSerialized = json.dumps(jsonSingle, indent=2, default=json_util.default, sort_keys=True)
        jsonObject = json.loads(jsonSerialized)
        if jsonObject.get(client_call_to_ringing):
            isTalkPlusCaller = jsonObject[client_call_to_ringing]
        if jsonObject.get(direction):
            callDirection = jsonObject[direction]
        jsonCallee = jsonObject.get(callee)
        if jsonCallee == None:
            continue
        if jsonCallee.get(client_network_type):
            network = jsonCallee[client_network_type]
        # check that call is not coming from talk+
        if isTalkPlusCaller == -1 and callDirection == "inbound" and network == "Wi-Fi" and jsonObject.get(trunkie_call_to_ringing):
            trunkieCallToRinging = jsonObject[trunkie_call_to_ringing]
            trunkieTable.append(int(trunkieCallToRinging*1000))
            if verbose:
                print "trunkie INVITE to talkplusWiFi RINGING: " + str(trunkieCallToRinging)
    return trunkieTable


#
# Parse a set of calls, check if they are IP-to-IP on TalkPlus
# return a list of call to ringing times on TalkPlus Wi-Fi and 3G
#
# verbose: Set to True for debug output, False for silent operation
# jsonResults: List of calls from mongo db
# calleeNetwork: One of 'Wi-Fi', 'UNKNOWN3G', or 'IP' (both) network type of the receiver
# returns list of call to ringing values
def talkPlusIPIP(verbose, jsonResults, calleeNetwork):
    clientCallToRingingTable = []

    printYellow("*** talk+ to talk+ IP-to-IP calls ***")
    for jsonSingle in jsonResults:
        clientCallToRinging = 0
        isTalkPlusCaller = -1
        callDirection = ''
        network = ''

        jsonSerialized = json.dumps(jsonSingle, indent=2, default=json_util.default, sort_keys=True)
        jsonObject = json.loads(jsonSerialized)
        if jsonObject.get(client_call_to_ringing):
            isTalkPlusCaller = jsonObject[client_call_to_ringing]
        if jsonObject.get(direction):
            callDirection = jsonObject[direction]
        jsonCallee = jsonObject.get(callee)
        if jsonCallee == None:
            continue
        if jsonCallee.get(client_network_type):
            network = jsonCallee[client_network_type]
        # print str(isTalkPlusCaller) + "/" + callDirection + "/" + network
        # check that call is not coming from talk+
        if isTalkPlusCaller != -1 and callDirection == "outbound":
            clientCallToRinging = jsonObject[client_call_to_ringing]
            if network == calleeNetwork:
                clientCallToRingingTable.append(clientCallToRinging)
                if verbose:
                    print "talk+ call to talk+ " + network + " RINGING"
            if calleeNetwork == "IP" and (network == 'Wi-Fi' or network == 'UNKNOWN3G'):
                clientCallToRingingTable.append(clientCallToRinging)
                if verbose:
                    print "talk+ call to talk+ " + network + " RINGING"
    return clientCallToRingingTable

#
# Parse a set of calls, check if they are going from Talk+ to SIP-trunk
# (both 3G and Wi-Fi talk+ clients), return client_call_to_ringing times
#
# verbose: Set to True for debug output, False for silent operation
# jsonResults: List of calls from mongo db
# timeset: Set 'talkplus', 'footee' or 'trunkieout'
# returns list of client call to ringing times
def talkPlusToSIPTrunk(verbose, jsonResults, timeset):
    clientCallToRingingTable = []
    trunkieCallToRingingTable = []
    footeeSetupTable = []

    printYellow("*** talk+ to SIP-trunk calls " + timeset + " ***")

    for jsonSingle in jsonResults:
        clientCallToRinging = -1
        trunkieCallToRinging = -1
        footeeSetup = -1
        isTalkPlusCaller = -1
        callDirection = ''
        calleeNetwork = ''

        jsonSerialized = json.dumps(jsonSingle, indent=2, default=json_util.default, sort_keys=True)
        jsonObject = json.loads(jsonSerialized)
        if jsonObject.get(client_call_to_ringing):
            isTalkPlusCaller = jsonObject[client_call_to_ringing]
        if jsonObject.get(direction):
            callDirection = jsonObject[direction]
        # callee.client_network_type will be present for SIP-trunk calls only
        jsonCallee = jsonObject.get(callee)
        if jsonCallee == None:
            continue
        if jsonCallee.get(client_network_type):
            calleeNetwork = jsonCallee[client_network_type]
        # check that call is not coming from talk+
        if isTalkPlusCaller != -1 and callDirection == "outbound" and calleeNetwork == '':
            if jsonObject.get(trunkie_call_to_ringing):
                trunkieCallToRinging = jsonObject[trunkie_call_to_ringing]
            else:
                if verbose:
                    printCall(jsonSingle)
                printRed("*** dropping call_id " + jsonObject[call_id] + " due to key error, missing " + trunkie_call_to_ringing + " ***")
                continue
            if jsonObject.get(client_call_to_ringing):
                clientCallToRinging = jsonObject[client_call_to_ringing]
            else:
                if verbose:
                    printCall(jsonSingle)
                printRed("*** dropping callid " + jsonObject[call_id] + " due key error, missing " + client_call_to_ringing + " ***")
                continue
            if jsonObject.get(footee_call_setup_time):
                footeeSetup = jsonObject[footee_call_setup_time]
            else:
                if verbose:
                    printCall(jsonSingle)
                printRed("*** dropping call_id " + jsonObject[call_id] + " due key error, missing " + footee_call_setup_time + " ***")
                continue

            trunkieCallToRingingTable.append(int(trunkieCallToRinging*1000))
            clientCallToRingingTable.append(clientCallToRinging)
            footeeSetupTable.append(footeeSetup)
            if verbose:
                print "call_id: " + jsonObject[call_id] + "caller:"+ jsonObject[caller_id_number] + ", dest:" + jsonObject[destination_number] + ", talkplus:" + str(clientCallToRinging)+ ", trunkie:"+str(trunkieCallToRinging) + ", footee:" + str(footeeSetup)
    if verbose:
        printYellow("talkplus to PSTN calls: " + str(len(clientCallToRingingTable)))
    if timeset == 'talkplus':
        return clientCallToRingingTable
    if timeset == 'footee':
        return footeeSetupTable
    if timeset == 'trunkieout':
        return trunkieCallToRingingTable
#
# Return start date, the given number of days back in time
#
# verbose: Set to True for debug output, False for silent operation
# numberOfDays: Set to the number of days ago we query database for
def queryStartDate(verbose, numberOfDays):
    # set number of days back in time where query should start
    startDate = datetime.datetime.now() - datetime.timedelta(numberOfDays,0)
    if verbose:
        printGreen(startDate)
    return startDate
#
# Retreive current date/time for end search
#
# verbose: set to True for debug output, False for silent operation
def queryEndDate(verbose):
    endDate = datetime.datetime.now()
    if verbose:
        printGreen(endDate)
    return endDate

def PlotPSTNToTalkPlus3G(dbcalls, filename):
    # PSTN to TalkPlus3G
    pstnToTalkPlus3G = sipTrunkToTalkPlus3G(False, dbcalls)
    if len(pstnToTalkPlus3G) == 0:
        printRed("*** no pstn to talk+ 3G calls ***")
        return
    # limit to 50 calls
    while len(pstnToTalkPlus3G) > 50:
        pstnToTalkPlus3G.pop(0)
    column3G = ['Talk+ Server SIP-INVITE to Talk+/3G RINGING']
    df = pd.DataFrame(pstnToTalkPlus3G, columns=column3G)
    xlabel = "Last " + str(len(pstnToTalkPlus3G)) + " PSTN incoming to Talk+/3G "
    ax = df.plot(kind='bar', colormap='gist_rainbow')
    ax.set_ylabel('milliseconds')
    ax.set_xlabel(xlabel)
    plt.savefig(filename)

def PlotPSTNToTalkPlusWiFi(dbcalls, filename):
    # PSTN to TalkPlus WiFi
    pstnToTalkPlusWiFi = sipTrunkToTalkPlusWiFi(False, dbcalls)
    # check for 0 calls
    if len(pstnToTalkPlusWiFi) == 0:
        printRed("*** no pstn to talk+ wifi calls ***")
        return
    # limit to 50 calls
    while len(pstnToTalkPlusWiFi) > 50:
        pstnToTalkPlusWiFi.pop(0)
    columnWiFi = ['Talk+ Server SIP-INVITE to Talk+/Wi-Fi RINGING']
    xlabel = "Last " + str(len(pstnToTalkPlusWiFi)) + " PSTN incoming to Talk+/Wi-Fi"
    df = pd.DataFrame(pstnToTalkPlusWiFi, columns=columnWiFi)
    ax = df.plot(kind='bar', colormap='gist_rainbow')
    ax.set_ylabel('milliseconds')
    ax.set_xlabel(xlabel)
    plt.savefig(filename)

def PlotTalkPlusToTalkPlus(dbcalls, filename):
    # PSTN to TalkPlus WiFi
    talkPlusToTalkPlus = talkPlusIPIP(False, dbcalls, 'IP')
    if len(talkPlusToTalkPlus) == 0:
        printRed("*** no talk+ to talk+ calls ***")
        return
    # limit to 50 calls
    while len(talkPlusToTalkPlus) > 50:
        talkPlusToTalkPlus.pop(0)
    columnIP = ['Talk+/IP call started to Talk+/IP RINGING']
    xlabel = "Last " + str(len(talkPlusToTalkPlus)) + " Talk+/IP to Talk+/IP"
    df = pd.DataFrame(talkPlusToTalkPlus, columns=columnIP)
    ax = df.plot(kind='bar', colormap='gist_rainbow')
    ax.set_ylabel('milliseconds')
    ax.set_xlabel(xlabel)
    plt.savefig(filename)

def PlotTalkPlusToPSTN(dbcalls, filename):
    # TalkPlus to PSTN SIP trunk
    tpToPSTNC = talkPlusToSIPTrunk(False, dbcalls, 'talkplus')
    if len(tpToPSTNC) == 0:
        printRed("*** no talk+ to pstn calls")
        return
    while len(tpToPSTNC) > 50:
        tpToPSTNC.pop(0)

    tpToPSTNT = talkPlusToSIPTrunk(False, dbcalls, 'trunkieout')
    while len(tpToPSTNT) > 50:
        tpToPSTNT.pop(0)

    tpToPSTNF = talkPlusToSIPTrunk(False, dbcalls, 'footee')
    while len(tpToPSTNF) > 50:
        tpToPSTNF.pop(0)

    index = 0
    while index < len(tpToPSTNC):
        # subtrace trunkieout (wait for SIP trunk) and footee setup time
        tpToPSTNC[index] = tpToPSTNC[index] - tpToPSTNT[index] - tpToPSTNF[index]
        index = index + 1

    columnPSTNT = 'Talk+ server INVITE to PSTN RINGING'
    columnPSTNF = 'Footee setup time'
    columnPSTNC = 'Talk+ client to server side'

    d = { columnPSTNT : pd.Series(tpToPSTNT), columnPSTNF : pd.Series(tpToPSTNF), columnPSTNC : pd.Series(tpToPSTNC) }
    xlabel = "Last " + str(len(tpToPSTNC)) + " Talk+/IP to PSTN calls"
    df = pd.DataFrame(d)
    ax = df.plot(kind='bar', stacked=True)
    ax.set_ylabel('milliseconds')
    ax.set_xlabel(xlabel)
    plt.savefig(filename)

##############################################################################
# main() :-)
##############################################################################

# Verify command line arguments
args = len(sys.argv)
if args != 3:
    printRed("usage: " + sys.argv[0] + " <username> <password>")
    exit(1)
else:
    username = sys.argv[1]
    password = sys.argv[2]

# Connect and authenticate
mongoDBConnect(True, 'mongodb://aewa-staging-mongodb:29017', username, password)

# Show collection (tables) - not required
# mongoDBCollection(True, collectionnname)

# This will dump a full example output - not required
# (just in case you don't remember the field names :-) )
# mongoDBDataTest()

# Set start date (to 30 days ago) and end time at now
start = queryStartDate(False, 30)
end = queryEndDate(False)

# query database, append to dbcalls list only - incoming calls to defined numbers
dbcalls = []
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215923", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215924", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215925", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215926", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215929", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215931", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215932", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215933", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215934", "+4746796655"))
dbcalls.extend(mongoDBGetCalls(False, start, end, "4767215935", "+4746796655"))

PlotPSTNToTalkPlus3G(dbcalls, 'pstn-to-talkplus3g.png')
PlotPSTNToTalkPlusWiFi(dbcalls, 'pstn-to-talkplusWiFi.png')

# query database, outgoing call to any number
dbcalls = []
dbcalls.extend(mongoDBGetCalls(False, start, end, None, "+4746796655"))
PlotTalkPlusToPSTN(dbcalls, 'talkplus-to-pstn.png')
PlotTalkPlusToTalkPlus(dbcalls, 'talkplus-to-talkplus.png')

# Disconnect from db
mongoDBDisconnect(False)

# terminate
printGreen("*** done ***")
exit(0)
