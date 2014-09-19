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

# db access
databasename = 'cdr-stats'
collectionname = 'cdr_common'
client = ''
db = ''
collection = []
username = ''
password = ''
callid = ''

# db fields
call_id = 'call_id'

# data lists
dbcalls = []

#
# Colorized output functions
# textString: text string to be output
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
    client = pymongo.MongoClient(server, read_preference=pymongo.ReadPreference.SECONDARY, tz_aware=True)
    db = client[databasename]

    jsonServerInfo = client.server_info()
    jsonServerSerialized = json.dumps(jsonServerInfo, indent=2, default=json_util.default, sort_keys=True )
    jsonServerObject = json.loads(jsonServerSerialized)
    if verbose == True:
        # print jsonServerSerialized
        print "Server:  " + jsonServerObject['sysInfo']
        print "Version: " + jsonServerObject['version']

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
# callId: call_id to retrieve
def mongoDBGetCallId(verbose, callid):
    global db
    global ringlist
    global footeelist
    jsonResults = []
    count = 0

    if verbose:
        printYellow("*** query database for calls ***")

    if callid != None:
        jsonResults = db[collectionname].find({"call_id": callid})
    if verbose:
        # output number of matching calls found
        if jsonResults.count() > 0:
            printGreen("*** found call_id ***")
        else:
            printYellow("*** call_id not found ***")

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


##############################################################################
# main() :-)
##############################################################################

# Verify command line arguments
args = len(sys.argv)
if args != 4:
    printRed("usage: " + sys.argv[0] + " <username> <password> <call_id>")
    exit(1)
else:
    username = sys.argv[1]
    password = sys.argv[2]
    callid = sys.argv[3]

# Connect and authenticate
mongoDBConnect(True, 'mongodb://aewa-staging-mongodb:29017', username, password)

# Show collection (tables) - not required
# mongoDBCollection(True, collectionnname)

# This will dump a full example output - not required
# (just in case you don't remember the field names :-) )
# mongoDBDataTest()

# query database, append to dbcalls list only - incoming calls to defined numbers
dbcalls = []
dbcalls = mongoDBGetCallId(True,  callid)
printCalls(dbcalls)

# Disconnect from db
mongoDBDisconnect(False)

# terminate
printGreen("*** done ***")
exit(0)
