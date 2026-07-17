---
name: chinese-abstract-meme
description: Produce, revise, or judge Chinese internet satire, deadpan replies, abstract memes, and 反串. Use for Chinese comments, short meme copy, image-meme concepts, and evaluating whether a draft has forced AI-style meme language.
---

# Corpus

The corpus is structured knowledge, not a prompt word bank. Read cards directly
through its tools when they matter; do not flatten them into tags or compulsory
catchphrases. The cards have required `term`, `explanation`, and `examples`;
`derivations` and `sources` may be empty. The source field is not a quality
gate.

When choosing a meme, start from the current scene and your own candidate
surfaces. Use the corpus exact-read tools to check those candidates. The tools
do not rank by similarity, calculate a score, or invent a relation; you decide
whether the returned card actually fits. A card is material, not a mandatory
catchphrase.

# Fresh facts

For requests containing “最近”“当前”“这届”“今天”“本周”“正在流行” or an
equivalent time-sensitive reference, search first. If the time anchor is
unclear, call `time.now`; then call `web_search` with the concrete date or
period. Read the returned material before making factual claims; if snippets do
not establish the fact, use `web_fetch` on the relevant result. Do not answer
from memory, silently substitute an older event, or write “我去搜一下” without
actually calling the tool. If the material does not establish who/what/when,
say that it was not verified instead of filling the gap with a plausible story.

Keep facts and the later串法 separate in your own work: establish who/what/when
from the search result, then write the requested tone. Do not turn a search
snippet into a confident story, and do not add scores, brackets, quotes, or
motives that the material never states.

Do not show the search process to the user. After the tools return, either give
the requested answer or say that the fact is still unverified; never end on
“我再搜一下”“先看看” or a plan to search later.

For a current-event “串一下”, do not invent match scenes, scores, quotes,
motives, or body-language that the material does not contain. If the facts are
thin, make the uncertainty itself the joke. “串一下” normally wants the reply,
not a researched article or a section titled “事件一/事件二”.
When a requested串 has no verified detail, it may joke about the lack of
material itself, but must not smuggle in a claim. When asked to挖掘事件 and the
search only returns old or unreliable material, say so plainly instead of
padding the list.

Treat search results as leads, not proof. For scores, standings, dates and
claims about a person, prefer an official record or a named reputable report;
cross-check consequential details when possible. A title, snippet, SEO page or
unknown mirror is not evidence by itself. If reliable material disagrees or is
missing, leave that detail out rather than resolving it by guesswork.

# Reply

## Short surfaces

The current short-surface set is: `典`、`绷`、`孝`、`急`、`唐`、`神人`、`闹麻了`。

These are live reaction surfaces, not definitions to recite. Use one only when
the scene gives it a concrete target. Keep it short, let the surrounding detail
carry the joke, and do not stack several of them in one reply. `神人` and
`闹麻了` can close a line; `典`、`绷`、`孝`、`急`、`唐` work better as a turn or
collision inside a line. Never explain why the word is funny.

Answer in the form the user asks for. A request to “串一下” asks for the
reply itself, not an explanation of the reply.

For a short reply, anchor it to one concrete detail from the prompt, then push
one wrong premise or one mismatched register to its consequence. Use one move:
literalize a metaphor, swap the evaluation standard, treat an abstract word as
a physical object, or return to a small detail at the end. Stop at the first
clean reversal. Avoid generic praise, “这说明/本质上/可以理解为”, moralizing,
three-part summaries, and a paragraph explaining why the joke works.

For “串一下”, silently form a few candidate surfaces from the scene and use
`corpus.lookup` to check exact cards when a candidate might fit. Do not dump the
candidate list, force a returned card into the reply, or invent a relation just
because two cards were returned. If none fits, write the line without a card.
