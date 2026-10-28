# M20 · Talk

**Owner:** BO8 · **Tool name:** `talk`

Talk is the conversation agent. The person asks why a look was chosen, or states a preference. Groq writes the sentence. Taste still owns the score.

## What it reads

From that person's taste memory, the same store the deck and the taste agent use:

- loves, from likes
- avoids, from stated dislikes
- wardrobe, from saved looks
- scores, from `score_map` on the candidates the orchestrator passes in

## What it writes

A lasting preference in the message is saved with `learn` on that `user_id` only. The words do not change a score, a verdict, a price, or a size.

## Call it

The orchestrator calls the `talk` tool. Directly:

`POST /m20/run` with `user_id`, `session_id`, `message`, and optional `candidates`.

Set `GROQ_API_KEY` in the environment. Without it, the agent says so and still returns the memory it can see.

## Do not use it for

Ranking is `taste`. An outfit from owned clothes is `stylist`. A buy verdict is `smartbuy`. The body is `tryon`.
