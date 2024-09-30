import { HoneyHive } from "honeyhive";
import { CreateEventRequestEventType } from "honeyhive/models/components";

const hhai = new HoneyHive({
    bearerAuth: process.env.HH_API_KEY,
});

// start an evaluation run
const evalRun = await hhai.runs.createRun({
    project: process.env.HH_PROJECT || "",
    name: "MY_EVAL_RUN",
    eventIds: [],
})

const runId = evalRun.runId;

// log your sessions
for (let i = 0; i < 5; i++) {
    const events = [
        {
            project: "Simple RAG",
            source: "playground",
            eventName: "Model Completion",
            eventType: CreateEventRequestEventType.Model,
        }
    ];

    const batchLogRes = await hhai.events.createEventBatch({
        events: events
    });

    const sessionId = batchLogRes.sessionId;

    // add the session to the evaluation
    const updateRes = await hhai.events.updateEvent({
        eventId: sessionId || "",
        metadata: {
            "run_id": runId
        }
    });
}

// let eventIdsEval: Array<string> = [];

// eventIdsEval.push(sessionId);

// await hhai.runs.updateRun({
//     runId,
//     UpdateRunRequest({
//         eventIds: eventIdsEval,
//         status: UpdateRunRequestStatus.COMPLETED,
//     })
// });