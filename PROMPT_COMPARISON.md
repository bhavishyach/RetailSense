# AI Enrichment Pipeline Prompt Comparison

## ORIGINAL PROMPT

```
You are an AI assistant that enriches retail product data. For each product below, return a JSON array of objects. Each object must contain the keys: asin, standardized_category, generated_description, attributes, confidence_score. The attributes field should be a JSON object containing extracted product attributes such as brand, size, color, material, or other salient information. Do not include any markdown formatting or explanatory text outside the JSON array. Ensure confidence_score is a number between 0.0 and 1.0. Use the exact field names specified.

Products JSON:
[JSON payload]

Return only valid JSON.
```

### Original Prompt Issues
- ❌ No example of expected output format
- ❌ No guidance on confidence_score calculation
- ❌ "Standardized category" not defined
- ❌ Attributes extraction not prioritized
- ❌ No error handling for incomplete data
- ❌ No edge case guidance
- ❌ Generic instruction on what makes "good" enrichment

---

## IMPROVED PROMPT (V2)

```
You are a retail product enrichment assistant. For each product, return a JSON array of objects with exact structure.

**Output Requirements:**
- Return ONLY a valid JSON array. No markdown, explanations, or text outside the array.
- Each object must have these exact keys: asin, standardized_category, generated_description, attributes, confidence_score

**Field Definitions:**

asin: Product identifier (must match input)

standardized_category: A clean, normalized product category. Rules:
  - Remove redundant qualifiers (e.g., "Supplies", "Products", "Accessories")
  - Fix obvious typos or category mismatches
  - Use common retail category names (Books, Electronics, Clothing, Sports & Outdoors, etc.)
  - If original category seems incorrect, infer correct category from title and price signals
  - Be concise (2-4 words max)
  - Example: "Shaving & Hair Removal Products" → "Shaving & Hair Removal"
           "Video Games" (for a book) → "Books" (inferred from title)

generated_description: A one-sentence product description (40-80 words). Rules:
  - Summarize what the product is
  - Mention key characteristics evident from title, price, or category
  - Be factual and avoid marketing language
  - Do NOT copy the title verbatim
  - Example: "A professional grooming tool set designed for beard and facial hair maintenance, featuring multiple attachments and a rechargeable battery."

attributes: A JSON object with extracted product attributes. Rules:
  - Extract 3-5 most relevant attributes for this product category
  - Only extract attributes you can reasonably infer from the data
  - Use lowercase key names
  - Prioritize: brand, intended_use, material, size_range, color
  - For unknown attributes, omit the key entirely (do NOT use "Unknown")
  - Examples:
    * Book: {"format": "hardcover", "genre": "fiction", "author": "J.K. Rowling"}
    * Clothing: {"material": "cotton blend", "size_range": "M-XL", "color": "blue"}
    * Electronics: {"brand": "Sony", "battery_life": "12 hours", "connectivity": "Bluetooth"}

confidence_score: A number 0.0-1.0 indicating enrichment confidence. Rules:
  - 0.8-1.0: High confidence. Clear category, complete product data, easily inferred attributes
  - 0.5-0.7: Medium confidence. Some data missing, category slightly unclear, or attributes partially inferred
  - 0.0-0.4: Low confidence. Very sparse data, contradictory signals, or impossible to determine category
  - Calculate based on: data completeness (title length, category clarity, price signals, review count), category confidence, attribute extractability

**Edge Cases:**
- If title is empty or <10 characters: set confidence_score ≤ 0.3
- If category appears completely wrong (e.g., "Video Games" for a book): infer correct category and set confidence_score 0.6-0.7
- If product attributes cannot be reasonably extracted: return empty attributes object {}
- If any field is missing or unclear, DO NOT invent data; use your best judgment or lower confidence_score

**Example Output:**
[
  {
    "asin": "B014TMV5YE",
    "standardized_category": "Luggage & Travel",
    "generated_description": "An expandable hardside roller luggage set featuring 29-inch checked capacity with TSA-approved locks and eight-wheel spinner design.",
    "attributes": {
      "material": "ABS + polycarbonate",
      "size": "29-inch",
      "wheels": "8-wheel spinner",
      "color": "black"
    },
    "confidence_score": 0.85
  },
  {
    "asin": "B07GDLCQXV",
    "standardized_category": "Luggage & Travel",
    "generated_description": "A durable hardcase luggage set with double-wheel design, featuring TSA locking mechanism and expandable capacity for medium travel needs.",
    "attributes": {
      "material": "PC + ABS hybrid",
      "size": "medium",
      "wheels": "double wheels",
      "color": "blue"
    },
    "confidence_score": 0.82
  }
]

Products JSON:
[JSON payload]

Return only the JSON array. Do not include any other text.
```

### Improved Prompt Strengths
- ✅ Explicit example output format with real data
- ✅ Clear rules for each output field
- ✅ Specific guidance on category standardization (with examples)
- ✅ Defined rules for description generation (word count, avoid marketing speak)
- ✅ Attributes extraction is prioritized (3-5 max, omit unknowns)
- ✅ Confidence score calculation explained with ranges and factors
- ✅ Edge case handling documented
- ✅ Data completeness checks (e.g., empty title → low confidence)
- ✅ Guidance for fixing category mismatches
- ✅ Concise, no token waste

---

## Key Differences

| Aspect | Original | Improved V2 |
|--------|----------|------------|
| Example Output | ❌ None | ✅ 2 real examples with all fields |
| Category Rules | ❌ Vague | ✅ Explicit rules + examples |
| Description Guidance | ❌ Minimal | ✅ Word count, tone, avoid copying title |
| Attributes | ❌ Generic list | ✅ Prioritized (3-5), omit unknowns, category-aware |
| Confidence Calculation | ❌ No guidance | ✅ Score ranges with reasoning factors |
| Edge Cases | ❌ Not addressed | ✅ Empty title, wrong category, missing data handled |
| Data Validation | ❌ No checks | ✅ Completeness checks built-in |
| Token Efficiency | ❌ Not mentioned | ✅ Implicit (no invented data, concise) |
| Error Handling | ❌ Not covered | ✅ Clear fallback rules |

---

## Recommendation

**Use Improved Prompt V2** for production because:

1. **Consistency** — Example output format ensures Claude follows exact structure
2. **Intelligence** — Rules enable actual enrichment (not just copying/trivial transforms)
3. **Reliability** — Edge cases and confidence logic prevent bad enrichments
4. **Evaluation** — Confidence score now meaningful for Gold layer metrics
5. **Cost** — Clear constraints prevent token waste (3-5 attributes, 40-80 word descriptions)

