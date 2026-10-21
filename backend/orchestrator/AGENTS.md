# Agents the orchestrator can call

The planner reads each agent's card and calls one tool. Agents do not call each other. A result can offer `next_actions`, and the planner may follow those, up to three tool calls. The writer then turns the facts into a sentence. It must keep every verdict, score, price, and size exactly as the agent returned them.

`session_id` is the chat thread. `user_id` is the person. Pass both on every call.

## Taste and talk

These two share one memory. One FashionCLIP model embeds every photo. Each person has their own rows, not their own neural net.

| | taste | talk |
| --- | --- | --- |
| Module | M19 | M20 |
| Use when | Rank an outfit or a purchase from what this person already liked | Discuss a choice, or remember something they just said |
| Reads | Likes, dislikes, and saved looks for this `user_id` | The same memory, plus scores from taste for the candidates it is given |
| Writes | A like, dislike, skip, or save | A stated like or dislike back into that same memory |
| Must not | Let another component rewrite its score | Invent or change a score, a verdict, a price, or a size |

A like with a 512-number vector moves the next ranking. A saved look is the wardrobe line talk can mention. A stated dislike is kept on that person and named in later answers.

`POST /m19/run` runs taste. `POST /m20/run` runs talk. Talk needs `GROQ_API_KEY` in the environment. Without the key it still returns the memory it can see.

## The other agents

| Tool | Module | Use when | Do not use when |
| --- | --- | --- | --- |
| wardrobe | M1 | List or file clothes this person owns | Choosing what to wear from taste |
| stylist | M2 | Build an outfit from owned clothes | The first ranking of a new outfit or purchase. Call taste first |
| profile | M5 | Read or update the style profile | A single like or dislike. That is taste |
| smartbuy | M6 | Decide whether to buy, with the price | Explaining taste. Call taste first, then smartbuy from `next_actions` |
| localshop | M7 | Find a piece in a local shop | Ranking by taste |
| tryon | M9 | Show the shirt, shorts, or vest on the SMPL-X body | Deciding the outfit. The body file stays on the machine that built it |
| share | M10 | Make a card the person can send | Choosing the outfit |
| trips | M11 | Plan clothes for a trip | A single outfit at home |
| challenges | M15 | A wear challenge | A purchase verdict |

Skills stay inside an owner and are not separate tools: wear log and calendar belong to stylist, the explanation writer belongs to the orchestrator, size belongs to smartbuy.

## Order for a normal request

1. An outfit or a purchase starts with **taste**, so the choice follows memory.
2. A question about why, or a new preference, goes to **talk**.
3. Follow `next_actions` when the person asked for that step: stylist to build the outfit, smartbuy to check the purchase, tryon to show it.
