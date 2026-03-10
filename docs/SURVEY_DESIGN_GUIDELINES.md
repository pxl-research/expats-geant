# Survey Design Guidelines

A concise reference for scientifically backed survey design principles, drawn from the
academic and professional literature. These guidelines inform M-Chat's suggestion and
validation engines.

---

## Primary Sources

| Source | Why it matters |
|---|---|
| **Dillman — Tailored Design Method (TDM)** | Foundational framework; social exchange theory, respondent burden reduction, visual design |
| **Krosnick & Presser — *Handbook of Survey Research*, Ch. 9** | Cognitive factors, satisficing, acquiescence bias — the most cited academic reference on question design |
| **AAPOR — Code of Professional Ethics & Best Practices** | Professional standard for survey research integrity, transparency, and validity |

---

## Question Wording

- **Be specific and concrete.** Vague questions produce vague answers. Replace "How do you feel about X?" with "How satisfied are you with X on a scale of 1–5?"
- **One thing at a time.** Avoid double-barreled questions (e.g., "Was the tool fast and easy to use?"). Split into two questions.
- **Neutral language.** Loaded or leading words skew responses. "Assistance to the poor" and "welfare" produce a 21-point swing in measured support (Krosnick & Presser).
- **No jargon.** Write for your least expert respondent.
- **Avoid negations.** "Do you not agree that…" is cognitively harder and prone to misreading.

## Response Scales

- **Optimal length: 4–7 points.** Scales shorter than 4 reduce discrimination; longer than 7 increase cognitive load and response bias.
- **Label every option.** Using only endpoint labels (e.g., "1 = Agree, 7 = Disagree") causes respondents to cluster near the labeled ends. Label all options or at minimum every other one.
- **Neutral midpoint: use with care.** Including a midpoint (e.g., "Neither agree nor disagree") reduces social desirability pressure but also lets disengaged respondents opt out. Omit when you need commitment; include when genuine neutrality is valid.
- **Consistent direction.** If positive=high in one question, keep it that way throughout the section.
- **Recency effect.** Respondents on long scales tend to pick options presented last. Counterbalance if possible.

## Question Order

- **General to specific.** Broad context-setting questions first; narrow follow-ups after.
- **Anchoring effect.** Early questions prime respondents for later ones. Ask about past behavior before current attitudes to reduce recall bias (~34% reduction per anchoring research).
- **Sensitive questions last.** Demographic or personal questions at the end reduce early drop-off.
- **Group related topics.** Jumping between unrelated topics increases cognitive load and confusion.
- **Randomize where possible.** For sets of similar questions (e.g., rating a list of items), randomize order per respondent to cancel out order effects.

## Cognitive Load

- **Shorter is better.** Each additional question increases burden and drop-off risk.
- **Progress indicators help.** Showing "Page 2 of 5" reduces abandonment.
- **Visual design matters as much as wording.** Font size, white space, and layout affect comprehension (Dillman TDM).
- **High cognitive load → acquiescence bias.** When questions are hard to process, respondents tend to agree with whatever is stated. This inflates "yes" responses by 10–15% under load (Applied Cognitive Psychology, 2025).
- **Satisficing.** Respondents who are unmotivated or cognitively taxed take shortcuts: picking the first plausible option, always selecting the midpoint, or straight-lining (same answer for every question). Design to minimize this: shorter surveys, interesting questions, clear benefits.

## Bias & Fairness

- **Social desirability bias.** People underreport stigmatized behaviors and overreport socially valued ones. Use indirect framing or anonymous collection for sensitive topics.
- **Acquiescence bias.** Respondents tend to agree with statements regardless of content. Counterbalance by mixing positively and negatively worded items.
- **Confirmation bias (designer side).** Avoid writing questions that assume a particular answer is "correct" or expected.
- **Accessibility.** Avoid color-only encoding; ensure questions are screen-reader compatible.

## Pre-Testing

- **Always pre-test.** Test with 5–10 members of the target population before deployment. Identify misinterpretations, ambiguous wording, and broken logic.
- **Cognitive interviewing.** Ask test respondents to think aloud as they answer — reveals confusion that standard pilot testing misses.
- **Check completion time.** Time your pre-test; adjust length if median completion exceeds your target.

## Structure & Flow

- **Sections with titles.** Grouping questions into labelled sections helps respondents orient and reduces perceived length.
- **Logical progression.** Funnel from broad to narrow within each section.
- **Conditional/branching logic.** Use skip logic to avoid asking irrelevant questions — but keep branching simple; complex trees confuse respondents and introduce errors.

---

## Quick Validation Checklist

Use this when reviewing a draft questionnaire:

- [ ] Each question asks about exactly one thing (no double-barreling)
- [ ] No leading or loaded language
- [ ] Response scale length is 4–7 options with all options labelled
- [ ] Scale direction is consistent throughout
- [ ] Sensitive / demographic questions are at the end
- [ ] No jargon or acronyms without definition
- [ ] Total survey length is appropriate for the audience
- [ ] Pre-tested with at least one representative respondent

---

## References

- Dillman, D. A. (2000). *Mail and Internet Surveys: The Tailored Design Method*. Wiley. ([PMC overview](https://pmc.ncbi.nlm.nih.gov/articles/PMC2328022/))
- Krosnick, J. A., & Presser, S. (2010). Question and questionnaire design. In *Handbook of Survey Research* (2nd ed.). ([PDF](https://web.stanford.edu/dept/communication/faculty/krosnick/docs/2010/2010%20Handbook%20of%20Survey%20Research.pdf))
- AAPOR. (2022). *Standards and Best Practices*. ([aapor.org](https://aapor.org/standards-and-ethics/))
- Cognitive load and acquiescence bias: *Applied Cognitive Psychology* (2025). ([doi](https://onlinelibrary.wiley.com/doi/10.1002/acp.70039))
- Anchoring and question order: Federal Reserve Bank of Boston Working Paper 13-15. ([PDF](https://www.bostonfed.org/-/media/Documents/Workingpapers/PDF/wp1315.pdf))
