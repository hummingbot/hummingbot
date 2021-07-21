"use strict";

var test = require('tape')
var LevelUp = require('level-test')();
var Sublevel = require('../');
var timestamp = require('monotonic-timestamp')

var db = Sublevel( LevelUp('test-level-sublevel_myDB', {valueEncoding: 'json'}) );
var groups = db.sublevel('groups');
var topics = db.sublevel('topics');

var timeGroup1 = timestamp();
var timeGroup2 = timestamp();

var timeTopic1 = timestamp();
var timeTopic2 = timestamp();
var timeTopic3 = timestamp();

console.log(timeTopic1,timeTopic2,timeTopic3)

test('reverse:true', function (t) {

  groups.put(timeGroup1, {name: 'Cats', title: 'discussion about cats!'}, function (err) {
    if (err) return console.log('Ooops!', err) 
    topics.put(timeGroup1 + '!' + timeTopic1, {title: 'dancing cats'}, function (err) {
      if (err) return console.log('Ooops!', err) 

      topics.put(timeGroup1 + '!' + timeTopic2, {title: 'cat in a box'}, function (err) {
        if (err) return console.log('Ooops!', err) 

   //     groups.put(timeGroup2, {name: 'Node.js', title: 'Node.js talk'}, function (err) {
   //       if (err) return console.log('Ooops!', err) 

          topics.put(timeGroup2 + '!' + timeTopic3, {title: 'Is there a good example for website without Express.js?'}, function (err) {
            if (err) return console.log('Ooops!', err) 

            var order = [
              timeGroup1 + '!' + timeTopic1,
              timeGroup1 + '!' + timeTopic2
            ].sort().reverse()

            topics.createReadStream({max: timeGroup1 + '!~', min: ''+timeGroup1, reverse: true })
           .on('data', function (data) {
              t.equal(data.key, order.shift())
              console.log('topic:', data.key, '=', data.value)
            })
            .on('end', function () {
              t.end()
              console.log('Stream ended')
            })
          });
        });
     // });
    });
  });

})
// output is not in revese order: 
// topic: 1366613791702!1366613791702.002 = { title: 'dancing cats' }
// topic: 1366613791702!1366613791702.003 = { title: 'cat in a box' }

