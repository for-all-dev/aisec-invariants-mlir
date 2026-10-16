# Embedding Model Extraction Threat Model

This note describes an authorized research framing for studying whether an embedding API can be copied through queries. It is intended for evaluating models you own, models you are authorized to test, or toy models built for security research.

## Core Threat Model

The attacker has black-box access to an embedding endpoint:

```text
input text -> output embedding vector
```

For each query, the attacker observes:

```text
x_i = attacker-chosen text
e_i = target_embedding(x_i)
```

They do not observe:

```text
hidden states
attention maps
layer inputs or outputs
gradients
token logprobs
checkpoint files
model weights
```

Under this view, the realistic goal is usually not exact weight recovery. The realistic goal is functional extraction: training a separate model that behaves similarly enough for retrieval, clustering, similarity scoring, or downstream classification.

## Step-By-Step Authorized Research Attack Model

### 1. Query The Target

The researcher sends a broad set of text inputs to the target embedding model and records the returned vectors:

```text
dataset = {
  (text_1, embedding_1),
  (text_2, embedding_2),
  ...
}
```

Better input coverage usually improves the extracted model. A research dataset might include short phrases, long passages, domain-specific terms, paraphrases, adversarial edge cases, multilingual text, and near-duplicate examples.

### 2. Choose A Student Model

The researcher chooses a separate model architecture:

```text
student(text) -> vector
```

The student architecture does not need to match the target architecture. It only needs enough capacity to approximate the target input-output behavior.

### 3. Train The Student On Target Outputs

The student is trained to make its output close to the target embedding:

```text
student(x_i) ~= target_embedding(x_i)
```

Common objective functions include:

```text
cosine_distance(student(x_i), e_i)
mean_squared_error(student(x_i), e_i)
```

This is model extraction or distillation. It can produce a useful substitute embedding model without revealing the original checkpoint.

### 4. Evaluate Functional Similarity

The extracted model should be evaluated by behavior, not by whether its weights match the target.

Useful evaluation questions:

```text
Does it produce similar nearest neighbors?
Does it preserve retrieval rankings?
Does it cluster examples similarly?
Does it give similar similarity scores?
Does it support the same downstream classifiers?
```

If the student preserves these behaviors, the attack has extracted practical utility even though it has not recovered the original weights.

### 5. Probe Architecture Clues

The interface may reveal limited metadata:

```text
embedding dimension
maximum input length
token usage patterns
normalization behavior
error behavior
latency patterns
```

These can provide hints about the target, but they generally do not identify the exact architecture or weights.

### 6. Handle Noisy Outputs

If the API returns randomized embeddings:

```text
returned_embedding = true_embedding + noise
```

then repeated queries may allow the attacker to estimate the clean embedding:

```text
average(noisy_outputs) ~= true_embedding
```

Defenses against this include sticky noise, query deduplication, rate limits, per-user query budgets, and monitoring for repeated or adaptive query patterns.

### 7. Distinguish Functional Extraction From Exact Weight Recovery

The normal embedding API exposes:

```text
text -> final vector
```

It does not expose:

```text
layer input -> layer output
```

Exact recovery of a layer becomes much more plausible if both the input and output of that layer are visible. For a linear layer:

```text
y = W x + b
```

enough independent observations of `(x, y)` can make `W` and `b` solvable by linear algebra. Normal embedding APIs do not provide this view, so exact checkpoint recovery is generally not identifiable from final embeddings alone.

## Security Takeaway

The main risk from exposing raw embeddings is not literal checkpoint recovery. The main risk is that the API acts as a deterministic, high-dimensional oracle that can be used to train a substitute model.

In short:

```text
raw embeddings leak representation geometry
representation geometry enables functional cloning
functional cloning can preserve commercial or operational utility
exact weight recovery usually requires stronger leakage
```

## Defensive Implications

To reduce extraction risk:

```text
avoid exposing raw embeddings when possible
perform retrieval or classification server-side
return top-k results, labels, or coarse scores instead of vectors
avoid exposing hidden states, gradients, or full logits
rate-limit repeated and adaptive query patterns
deduplicate repeated inputs
use sticky noise if randomized outputs are needed
track per-user query budgets
monitor for extraction-style behavior
```

The strongest design is to keep the embedding vector internal and expose only the narrow downstream result the user actually needs.

## Differential Privacy-Style Defenses

Differential privacy does not directly encrypt or hide model weights. Classic DP is usually used to limit how much the trained model reveals about any one training example. For model extraction, the useful idea is DP-style output perturbation: make each observed embedding less informative, then limit how many informative observations an attacker can collect.

The defensive goal is:

```text
make target_embedding(text) expensive or unreliable to imitate
```

not:

```text
make weights mathematically unrecoverable by DP alone
```

### 1. Bound The Embedding Output

First, normalize or clip the embedding so that one response has bounded scale:

```text
e = target_embedding(text)
e = e / ||e||
```

This matters because noise must be calibrated to a bounded output. If embeddings are unit-normalized, the maximum L2 distance between two embeddings is at most `2`.

### 2. Add Gaussian Noise

Return a noisy embedding:

```text
noise ~ Gaussian(0, sigma^2 I)
e_noisy = normalize(e + noise)
return e_noisy
```

Larger `sigma` makes extraction harder but hurts retrieval quality. Smaller `sigma` preserves utility but may do little to stop a student model from learning the embedding function.

### 3. Make Noise Sticky

Fresh random noise is vulnerable to averaging:

```text
average(e + noise_1, e + noise_2, ..., e + noise_n) ~= e
```

To reduce this, use sticky noise: for the same user and same normalized input, return the same randomized vector.

Conceptually:

```text
noise_seed = HMAC(server_secret, user_id || canonicalized_text)
noise = GaussianNoise(seed = noise_seed)
e_noisy = normalize(e + noise)
```

This prevents repeated identical queries from revealing new independent samples of the noise.

### 4. Canonicalize And Deduplicate Inputs

Attackers may try tiny text changes to bypass sticky noise:

```text
"hello world"
"hello world "
"Hello world"
"hello  world"
```

Before assigning a noise seed or query budget, canonicalize inputs where possible:

```text
trim whitespace
normalize unicode
collapse repeated spaces
optionally lowercase for non-case-sensitive applications
```

Near-duplicate detection can also help, but it must be tuned carefully because aggressive deduplication can harm legitimate use.

### 5. Track A Query Budget

DP composes: more queries mean more total leakage. The API should track how many high-information answers each user receives.

Example policy:

```text
first N queries: return noisy embeddings
after N queries: increase noise
after M queries: return only coarse similarity buckets
after K queries: require review or block
```

This is especially important for broad, adaptive query patterns designed to train a substitute model.

### 6. Prefer Coarse Outputs Over Raw Vectors

The best reduction is to avoid returning embeddings at all. Instead, use embeddings internally and return a narrower result:

```text
query text -> top-k document IDs
query text -> similarity bucket
query text -> class label
query text -> yes/no threshold result
```

DP-style noise can be applied before the server-side retrieval or classification step, and the user only sees the final limited output.

### 7. Measure The Defense Empirically

Evaluate both utility and extraction resistance:

```text
retrieval quality before and after noise
student model accuracy before and after noise
number of queries needed to clone useful behavior
effect of repeated-query averaging
effect of near-duplicate query attacks
```

A useful experiment is:

```text
train a student on clean embeddings
train a student on noisy embeddings
train a student on sticky-noisy embeddings
compare nearest-neighbor and retrieval-ranking agreement
```

### Practical Defense Stack

For embedding APIs, DP-style output noise works best as one layer in a broader defense:

```text
normalize or clip embeddings
add calibrated noise
use sticky per-user noise
deduplicate repeated inputs
limit query volume
detect adaptive extraction patterns
return coarse task outputs when possible
avoid exposing hidden states, gradients, or logits
```

The main tradeoff is utility. If the noise is small, extraction may still work. If the noise is large, retrieval quality may degrade. The most robust design is therefore to keep raw embeddings internal and expose only the minimum downstream answer.
