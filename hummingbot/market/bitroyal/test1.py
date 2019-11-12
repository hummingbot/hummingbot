#!/usr/bin/env python

import json

testStr = { 
        "m":0,
        "i":0,
        "n":"ping",
        "o":""
}

testStr = json.dumps(testStr)
print(testStr)
