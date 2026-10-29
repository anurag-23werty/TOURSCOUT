import { parseSse } from "./api";

describe("parseSse", () => {
  it("parses complete events and keeps the unfinished tail", () => {
    const chunk = 'event: thread\ndata: {"thread_id":"t1"}\n\nevent: step\ndata: {"node":"intake","message":"ok"}\n\nevent: pl';
    const { events, rest } = parseSse(chunk);
    expect(events).toEqual([
      { kind: "thread", data: { thread_id: "t1" } },
      { kind: "step", data: { node: "intake", message: "ok" } },
    ]);
    expect(rest).toBe("event: pl");
  });

  it("handles an event split across network chunks", () => {
    const first = parseSse('event: plan\ndata: {"artist":');
    expect(first.events).toHaveLength(0);
    const second = parseSse(first.rest + '"Hovvdy"}\n\n');
    expect(second.events).toEqual([{ kind: "plan", data: { artist: "Hovvdy" } }]);
  });
});
