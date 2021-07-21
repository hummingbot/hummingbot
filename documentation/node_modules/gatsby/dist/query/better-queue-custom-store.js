"use strict";

exports.__esModule = true;
exports.memoryStoreWithPriorityBuckets = memoryStoreWithPriorityBuckets;

function memoryStoreWithPriorityBuckets() {
  let uuid = 0;
  /**
   * Task ids grouped by priority
   */

  const queueMap = new Map();
  /**
   * Task id to task lookup
   */

  const tasks = new Map();
  /**
   * Task id to priority lookup
   */

  const taskIdToPriority = new Map();
  /**
   * Lock to running tasks object
   */

  const running = {};
  let priorityKeys = [];

  const updatePriorityKeys = () => {
    priorityKeys = Array.from(queueMap.keys()).sort((a, b) => b - a);
  };

  const addTaskWithPriority = (taskId, priority) => {
    let needToUpdatePriorityKeys = false;
    let priorityTasks = queueMap.get(priority);

    if (!priorityTasks) {
      priorityTasks = [];
      queueMap.set(priority, priorityTasks);
      needToUpdatePriorityKeys = true;
    }

    taskIdToPriority.set(taskId, priority);
    priorityTasks.push(taskId);
    return needToUpdatePriorityKeys;
  };

  return {
    connect: function (cb) {
      cb(null, tasks.size);
    },
    getTask: function (taskId, cb) {
      // @ts-ignore
      cb(null, tasks.get(taskId));
    },
    deleteTask: function (taskId, cb) {
      if (tasks.get(taskId)) {
        tasks.delete(taskId);
        const priority = taskIdToPriority.get(taskId);

        if (priority) {
          var _queueMap$get;

          const priorityTasks = (_queueMap$get = queueMap.get(priority)) !== null && _queueMap$get !== void 0 ? _queueMap$get : [];
          priorityTasks.splice(priorityTasks.indexOf(taskId), 1);
          taskIdToPriority.delete(taskId);
        }
      }

      cb();
    },
    putTask: function (taskId, task, priority = 0, cb) {
      const oldTask = tasks.get(taskId);
      tasks.set(taskId, task);
      let needToUpdatePriorityKeys = false;

      if (oldTask) {
        const oldPriority = taskIdToPriority.get(taskId);

        if (oldPriority && oldPriority !== priority) {
          var _queueMap$get2;

          const oldPriorityTasks = (_queueMap$get2 = queueMap.get(oldPriority)) !== null && _queueMap$get2 !== void 0 ? _queueMap$get2 : [];
          oldPriorityTasks.splice(oldPriorityTasks.indexOf(taskId), 1);

          if (addTaskWithPriority(taskId, priority) // ||
          // oldPriorityTasks.length === 0
          ) {
              needToUpdatePriorityKeys = true;
            }
        }
      } else {
        needToUpdatePriorityKeys = addTaskWithPriority(taskId, priority);
      }

      if (needToUpdatePriorityKeys) {
        updatePriorityKeys();
      }

      cb(null);
    },
    takeFirstN: function (n, cb) {
      const lockId = String(uuid++);
      let remainingTasks = n;
      let needToUpdatePriorityKeys = false;
      let haveSomeTasks = false;
      const tasksToRun = {};

      for (const priority of priorityKeys) {
        var _tasksWithSamePriorit;

        const tasksWithSamePriority = queueMap.get(priority);
        const grabbedTaskIds = (_tasksWithSamePriorit = tasksWithSamePriority === null || tasksWithSamePriority === void 0 ? void 0 : tasksWithSamePriority.splice(0, remainingTasks)) !== null && _tasksWithSamePriorit !== void 0 ? _tasksWithSamePriorit : [];
        grabbedTaskIds.forEach(taskId => {
          // add task to task that will run
          // and remove it from waiting list
          const task = tasks.get(taskId);

          if (task) {
            tasksToRun[taskId] = task;
            tasks.delete(taskId);
            taskIdToPriority.delete(taskId);
            haveSomeTasks = true;
          }
        });
        remainingTasks -= grabbedTaskIds.length;

        if ((tasksWithSamePriority === null || tasksWithSamePriority === void 0 ? void 0 : tasksWithSamePriority.length) === 0) {
          queueMap.delete(priority);
          needToUpdatePriorityKeys = true;
        }

        if (remainingTasks <= 0) {
          break;
        }
      }

      if (needToUpdatePriorityKeys) {
        updatePriorityKeys();
      }

      if (haveSomeTasks) {
        running[lockId] = tasksToRun;
      }

      cb(null, lockId);
    },
    takeLastN: function (n, cb) {
      // This is not really used by Gatsby, but will be implemented for
      // completion in easiest possible way (so not very performant).
      // Mostly done so generic test suite used by other stores passes.
      // This is mostly C&P from takeFirstN, with array reversal and different
      // splice args
      const lockId = String(uuid++);
      let remainingTasks = n;
      let needToUpdatePriorityKeys = false;
      let haveSomeTasks = false;
      const tasksToRun = {};

      for (const priority of priorityKeys.reverse()) {
        var _queueMap$get3;

        const tasksWithSamePriority = (_queueMap$get3 = queueMap.get(priority)) !== null && _queueMap$get3 !== void 0 ? _queueMap$get3 : [];
        const deleteCount = Math.min(remainingTasks, tasksWithSamePriority.length);
        const grabbedTaskIds = tasksWithSamePriority.splice(tasksWithSamePriority.length - deleteCount, deleteCount);
        grabbedTaskIds.forEach(taskId => {
          // add task to task that will run
          // and remove it from waiting list
          tasksToRun[taskId] = tasks.get(taskId);
          tasks.delete(taskId);
          taskIdToPriority.delete(taskId);
          haveSomeTasks = true;
        });
        remainingTasks -= grabbedTaskIds.length;

        if (tasksWithSamePriority.length === 0) {
          queueMap.delete(priority);
          needToUpdatePriorityKeys = true;
        }

        if (remainingTasks <= 0) {
          break;
        }
      }

      if (needToUpdatePriorityKeys) {
        updatePriorityKeys();
      }

      if (haveSomeTasks) {
        running[lockId] = tasksToRun;
      }

      cb(null, lockId);
    },
    // @ts-ignore
    // getRunningTasks is an extension to the interface, and is only used in the tests
    getRunningTasks: function (cb) {
      cb(null, running);
    },
    getLock: function (lockId, cb) {
      cb(null, running[lockId]);
    },
    releaseLock: function (lockId, cb) {
      delete running[lockId];
      cb(null);
    }
  };
}
//# sourceMappingURL=better-queue-custom-store.js.map