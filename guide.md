# Labour Unrest Classification Guide

Yes—this is doable, and it's a fairly standard "news → event detection → event de-duplication → event analytics" problem. The main thing to internalize early is that you're not primarily classifying articles; you're trying to identify and track strike events (with attributes), and articles are noisy, duplicated, and often refer to the same underlying event.

Below is how I'd structure the solution space and a concrete PoC plan.

---

## Feasibility and the Two Core Problems

### 1) "Is this about a strike / labour unrest?"

This part is very feasible with:
- a small amount of labeled data,
- active learning,
- and a multilingual transformer (or Greek-specific transformer).

Even a strong baseline (TF‑IDF + linear model) often works surprisingly well as a first pass.

### 2) "Don't double-count the same strike across many articles"

This is the harder and more "product-defining" part.

You need event linking (aka "story clustering" / "event deduplication"):
- detect that article A and B refer to the same strike action,
- despite paraphrases, political framing, updates, and follow-up coverage.

In practice, you'll want both:
- near-duplicate detection (syndicated / copied content),
- event-level clustering (many distinct articles about one strike).

---

## Recommended Architecture: A Pipeline, Not a Single Model

A robust design is:

1. Ingest & normalize articles
2. Article-level classifier: strike/unrest vs not
3. Attribute extraction (sector, scope, location, actors, dates, etc.)
4. Event linking / clustering: group strike-articles into events
5. Event-level scoring & analytics: count events, severity, trends

This reduces "double counting" by design, because you count clusters/events, not articles.

---

## Model Choices: Do You Need an LLM?

You don't strictly need an LLM to build a working PoC. But an LLM can help in two very high-leverage places:
- bootstrapping labels and speeding manual annotation,
- structured attribute extraction (especially multilingual + messy political language).

For production inference at scale, a fine-tuned encoder model is often cheaper and more consistent, while an LLM is used for:
- hard cases,
- auditing,
- extraction where you really need high recall on subtle phrasing.

So the practical answer is: **a hybrid approach is usually best**.

---

## Encoder Models That Make Sense for Greece + Multilingual

### Option A: Greek-specific encoder (likely best for Greek-only)

GreekBERT exists and is widely used as a strong Greek baseline.
- **Pros:** strong Greek representations.
- **Cons:** if you later expand to other languages, you'll either train multiple models or switch architectures.

### Option B: Multilingual encoder (best if you want "Greece now, other countries later")

XLM‑RoBERTa (XLM‑R) is a standard multilingual encoder trained across many languages and commonly used for cross-lingual classification.
- **Pros:** one model for Greek + others, easy multilingual scaling.
- **Cons:** might underperform a Greek-only model on some nuances.

### Handling Length (BERT-style 512 token limit)

Most encoders have ~512 token max positions (including XLM‑R config defaults).

Practical ways around this:
- Headline + lead paragraph (often enough for strikes)
- Sliding window (chunk the article, classify chunks, then aggregate)
- Hierarchical: embed chunks → pool → classify
- Long-context encoder (Longformer-style)

There are XLM‑R → Longformer variants supporting longer sequences (e.g., 4096 tokens).
And empirically, some work suggests the gains from long-context models for classification can be task-dependent; larger encoders can outperform long-context variants, and mixing short+long examples in fine-tuning can help.

> **For a PoC:** start with sliding windows + aggregation; only switch to long-context models if you can show it matters.

---

## Where an LLM Helps (and Where It Doesn't)

### High-leverage uses

**Annotation assistant**
- LLM proposes: is_strike, sector, scope, date, actors, etc.
- Human confirms/edits.
- This can dramatically reduce labeling time.

**Structured extraction**
- If you force JSON schema outputs, you can build a reliable extractor.
- OpenAI supports "Structured Outputs" (JSON schema adherence) via function calling or response formats.

**Hard-case adjudication**
- When the encoder is uncertain or the content is tricky (propaganda, implied strikes, euphemisms).

### Less compelling uses

Using an LLM as the only classifier for everything can be expensive and harder to keep consistent over time (unless your volume is low).

---

## The "Double Count" Solution: Event Entity + Clustering

You'll want two layers:

### 1) Near-duplicate detection (syndication / copy-paste)

- Normalize text (strip boilerplate).
- Hashing approach like SimHash / MinHash on shingles.
- If similarity > threshold → mark as duplicates, keep one canonical.

This solves "same article republished."

### 2) Event-level linking (many articles, same strike)

Define a `StrikeEvent` schema and extract it per article. Minimum useful fields:
- `event_date_start` (or "action date" if it's a 24h strike)
- `location` (city/region + country)
- `sector` (transport, education, health, etc.)
- `actors` (union, workers group, company/agency)
- `scope` (company/local/regional/national/general strike)
- *optional:* duration, demands, services affected

Then cluster articles into events using a combination of:
- semantic similarity (embedding of title+summary),
- entity overlap (same union/company/location),
- temporal proximity (within a time window).

In practice, a simple and strong event-key baseline is:

```
event_key = normalize(sector + main_actor + location + action_date_bucket)
```

…and then you merge clusters when the key matches or similarity is high.

You'll still have edge cases (multi-day strikes, rolling stoppages, recurring strikes), but it's already enough to stop obvious double counting.

---

## What Kind of Labels You Should Create

Start simple; add sophistication after the PoC is stable.

### PoC Label Schema (recommended)

- **Binary:** `strike_or_labour_unrest` (yes/no)
- **If yes:**
  - `event_type`: {strike, work_stoppage, protest, lockout, union_call, negotiation, other}
  - `sector`: coarse taxonomy (10–20 buckets)
  - `scope`: {company/local/regional/national/general}
  - `action_date`: date or unknown
  - `location`: city/region
  - `primary_actor`: union/occupation/company/agency

This is enough to:
- classify,
- cluster,
- count unique events,
- build basic analytics.

---

## PoC Plan: Step-by-Step

### Step 0: Decide what you are counting

Write down explicitly:

> "We count unique strike events (clusters), not articles."

Define how you treat:
- multi-day strikes (one event with duration vs one per day),
- recurring strikes (same actor repeated weekly),
- "announced strike" vs "strike happened" vs "strike ended."

This prevents rework later.

### Step 1: Ingest and store articles (with provenance)

**Goal:** reproducible dataset.

Collect from your selected Greek sites via RSS/sitemaps/search pages.

Store:
- raw HTML,
- extracted clean text,
- title, author (if any),
- published timestamp,
- URL + canonical URL,
- site name,
- scrape timestamp.

Keep the raw HTML so you can re-extract text when your parser improves.

> **Also:** check robots.txt / terms and consider whether you need agreements/licenses for systematic scraping (especially if this becomes production).

### Step 2: Text cleaning + normalization

- Boilerplate removal (menus, related links, cookie text).
- Language detection (Greek vs other).
- Normalize punctuation, quotes, whitespace.

Keep both:
- full text,
- "short view" (title + first N paragraphs).

### Step 3: Candidate generation (high recall)

Before any ML, create a high-recall filter so you're not labeling random news.

**Greek keyword families:**
- απεργία, απεργούν, γενική απεργία
- στάση εργασίας
- κινητοποίηση (careful: broad)
- συνδικάτο, ΓΣΕΕ, ΑΔΕΔΥ, σωματείο, ομοσπονδία
- "μπλοκάρουν", "παραλύει", "δεμένα πλοία", etc. (domain-specific)

This filter is not your final classifier; it's to:
- build an initial pool of likely positives,
- and a controlled set of "hard negatives."

### Step 4: Build the annotation loop (human + LLM assistance)

Use an annotation tool (Label Studio / Prodigy / custom UI).

**Workflow that works well:**
1. Show article text (short view + expand).
2. Show LLM-suggested labels + extracted JSON.
3. Annotator clicks "accept/edit".

If you use OpenAI, structured JSON extraction is much easier if you enforce a schema (Structured Outputs / function calling).

If you want to speed up coding the PoC, Codex CLI can help implement the pipeline locally (it's designed to read/edit/run code in a directory).

**Important:** treat LLM outputs as suggestions, not truth. Store:
- `llm_suggestion`,
- `human_final`,
- and disagreements (useful for prompt/model improvements).

### Step 5: Start with two baselines (fast feedback)

Train two article-level classifiers:

**TF‑IDF + Logistic Regression**
- Extremely strong baseline for news topic detection.
- Great for debugging labeling quality and identifying leakage.

**Encoder fine-tune**
- If Greek-only: GreekBERT
- If multilingual roadmap: XLM‑R

For length, start with:
- title + lead (or),
- sliding windows with max/mean pooling of chunk logits.

### Step 6: Active learning (your labeling accelerator)

Once you have an initial model:
1. Run it on a large unlabeled pool.
2. Sample for annotation using:
   - uncertainty sampling (prob near 0.5),
   - plus diversity sampling (avoid 100 near-duplicates).

This quickly improves the decision boundary with fewer labels.

### Step 7: Attribute extraction (minimal viable)

You have two choices:

**A) LLM extractor (fastest PoC)**
- Prompt → JSON fields (sector/scope/date/location/actor).
- Human corrects on a subset.
- Later, you can distill into smaller models.

**B) Train extractors**
- NER model + rule-based postprocessing.
- Harder in Greek unless you already have tooling.

For a PoC, I'd do A first.

### Step 8: Event clustering to avoid double counting

After you have strike-positive articles + extracted fields:
1. Build an article embedding (title + short summary).
2. Build a feature vector from extracted fields.
3. Cluster with time-window constraints (e.g., 7–14 day window).

**Start simple:**
- rule-based "event_key" + fuzzy matching,

**then move to:**
- embedding similarity + clustering (DBSCAN/HDBSCAN style).

**How you evaluate this in a PoC:**
- sample 50–100 clusters,
- manually judge: cluster purity (same event?) and fragmentation (same event split across clusters?).

### Step 9: Event-level scoring

Don't overcomplicate early.

**Example PoC severity score:**
- `scope`: national/general > regional > local > single company
- `sector weights` (transport disruptions often higher impact than small office stoppage)
- `duration`: 24h vs multi-day vs indefinite (if detectable)

**Output:**
- event counts per week,
- severity-weighted index,
- sector breakdown.

---

## What "Success" Looks Like for a PoC

You should aim for these deliverables:

| Deliverable | Details |
|-------------|---------|
| **Reproducible dataset** | ingestion + stored raw HTML + clean text |
| **A labeled seed set** | a few hundred articles is enough to see signal (especially with active learning) |
| **Article classifier with measurable performance** | precision/recall on a held-out set; explicit error analysis (false positives like "strike" in non-labour sense) |
| **Event deduplication that's "good enough"** | demonstrably reduces double counting; cluster quality checked on a sample |
| **Basic analytics** | event timeline + sector/scope distributions |

---

## Practical Recommendation for Your First Iteration

If you want the fastest path to a convincing PoC:

| Component | Recommendation |
|-----------|----------------|
| **Classifier** | XLM‑R (multilingual) or GreekBERT (Greek-only) fine-tuned on title+lead; sliding window if needed |
| **Extractor** | LLM JSON schema extraction (human-verified on a sample) |
| **Dedup** | SimHash for near-duplicates + rule-based event_key clustering, then upgrade to embedding clustering |

This combination usually gets you to "useful signal + not double-counting wildly" without needing a large bespoke dataset up front.

---

If you want, I can propose a concrete label taxonomy for Greek labour news (sector buckets + scope definitions + "event happened vs announced" distinctions) and a JSON schema/prompt template that's specifically tuned to minimize LLM hallucinations for extraction.
