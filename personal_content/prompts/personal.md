Write one Xiaohongshu image/text post in the personal style, using only the supplied canonical JSON as factual authority.

Return exactly one JSON object with exactly these keys: schema_version, style, title, body, tags, images. Set schema_version to 1 and style to "personal". Copy all image paths exactly once; their order may be chosen intentionally. Use non-empty string arrays for tags and images.

Make this feel like the source author's own record: preserve useful original phrases, concrete details, and source language; use natural pacing and light structure; do not force a tutorial. Do not add experiences, dates, numbers, statistics, achievements, expertise, opinions, events, conclusions, or image claims absent from canonical. Avoid generic introductions/conclusions, clickbait, excessive headings/symmetry/emoji, corporate language, and formulaic transitions such as 首先、其次、最后 or 值得一提的是. Output JSON only.
