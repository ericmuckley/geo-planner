# Routing on Vercel: two options

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

**Decision, October 16:** focus on the US and use a free external service first. Revisit self-hosting when usage limits or payment requirements appear. Worldwide expansion is deferred. See [the selected service and setup](../us-routing-service.md). The comparison below records the tradeoffs behind that choice. The hosted one-hour range limit leaves the original 10–12-hour requirement unmet; the current priority is [brainstorming our own long-range implementation](long-range-routing-brainstorm.md) before deployment.

**Both options keep your website and application backend in one fullstack TanStack Start app on Vercel.** The choice is where driving routes and reachable areas are calculated. Worldwide road data needs storage outside the app's deployment bundle in either case.

| | External routing API | Routing inside Vercel |
| --- | --- | --- |
| What happens | Your Vercel backend asks a routing provider for the result. | Your Vercel backend runs the routing software and loads road files from separate storage. |
| Who maintains worldwide roads? | The provider. | We do: obtain the data, build it, host it, and update it. |
| Costs | Provider subscription/query fees, plus normal Vercel usage. | Vercel computing, file storage, downloads, and road-data preparation. |
| Main benefit | Fastest path to a working worldwide app; less infrastructure to maintain. | More control over routing rules and future algorithm experiments. |
| Main limitation | Provider limits, prices, and availability; long driving budgets may need a special plan or may be unsupported. | More engineering and testing; fresh Vercel instances must download road files, which can be slow and expensive. |
| Who receives coordinates? | Your backend and the routing provider. | Your backend; file-storage requests can also reveal the approximate region. |

The internal option is still experimental. Our local Node test worked, but fetched about **279 MB of road tiles for its first 60-minute San Diego query**. That was a local test, not a worldwide test or a Vercel deployment. [Vercel's execution and memory limits](https://vercel.com/docs/functions/limitations) also need validation.

**Recommendation: use an external routing API for the first worldwide version.** Keep the routing adapter replaceable so we can later move calculations inside Vercel if measurements justify it. Openrouteservice is selected for the US first version: its free plan supports 60-minute driving contours. Longer budgets need a later backend decision. The adapter is connected with the user-configured key, and five US locations plus the default browser contour work. See [measured hosted verification](hosted-routing-verification.md). Actual Vercel deployment and nationwide correctness remain to be qualified.
