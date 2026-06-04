# Participant Information Sheet — Template

> **For deployers.** This template is based on the European Commission's
> Horizon Europe model Participant Information Sheet, adapted to the Expats
> project and aligned with GDPR (Regulation (EU) 2016/679).
>
> Replace every `<PLACEHOLDER>` with your institution-specific value. Before
> distribution to participants, have the result reviewed by your Data
> Protection Officer and (where applicable) by your institutional ethics
> committee. This template is **not** a substitute for institutional review.
>
> Translate as needed; written informed consent under Belgian and EU practice
> must be provided in a language the participant understands.

---

## Study title

**Pilot evaluation of the Expats platform: Explainable Autofill for Trustworthy Surveys**

## Who is running this study?

This study is run by `<INSTITUTION>` in the context of the GÉANT Innovation
Programme 2026 project *Expats* (Explainable Autofill for Trustworthy
Surveys), led by PXL University College (Belgium) and funded by GÉANT.

Principal Investigator: `<PI_NAME>`, `<PI_TITLE>`, `<INSTITUTION>`
Contact: <`<PI_EMAIL>`>

## Why are we doing this study?

We are evaluating two AI assistants:

- **Shape**, which helps administrators design clear, consistent
  questionnaires.
- **Cue**, which helps respondents draft answers based on documents they
  provide, with citations showing where each suggestion came from.

We want to learn whether these tools save time, improve completeness and
citation accuracy, and how often users accept, edit, or reject the AI's
suggestions.

## Why have you been invited?

You have been invited because you are an adult member of `<INSTITUTION>`
(staff, student, or external collaborator) who works with surveys, either as
a designer or a respondent.

This pilot does not target vulnerable populations, children, patients, or
any health-research context.

## Is participation voluntary?

Yes. Participation is entirely voluntary. You can decline to participate,
and you can withdraw at any time during the study without giving a reason.

**Withdrawal will have no effect on your academic standing, your employment,
or any other relationship with `<INSTITUTION>`.**

If you withdraw, you can ask that data you have already provided be deleted
(see "Your data protection rights" below).

## What will participation involve?

- One or more sessions of approximately `<DURATION>` using the Expats web
  interface.
- You may upload documents (text, PDFs, possibly URLs) relevant to a
  questionnaire you are working on.
- The AI assistant will read the documents and propose answers or
  improvements. You decide whether to accept, edit, or reject each
  suggestion.
- We will record log data about your interactions: what you uploaded, what
  the AI suggested, what you accepted or edited, and how long each step
  took.
- You may optionally complete a short feedback questionnaire at the end of
  each session.

## What are the possible benefits?

You may save time on questionnaire work and produce more consistent
results. Your feedback will help shape a tool that the wider European
research and education community can use.

## What are the possible risks?

- **Documents you upload may contain personal data.** Please do **not**
  upload documents containing **special-category data** as defined in
  Article 9 GDPR (health, religious beliefs, political opinions, sexual
  orientation, biometric or genetic data, trade-union membership, ethnic
  origin) unless you have a specific lawful basis to do so and have
  separately consented to such processing. Expats provides guidance and
  filters to reduce accidental processing, but the final decision is yours.
- **The AI's suggestions are advisory only.** They may be wrong,
  incomplete, or biased. You remain responsible for the final content of
  any survey or response.
- **Uploaded materials must respect copyright and third-party rights.**
  Please upload only materials you have the right to use.
- A Data Protection Impact Assessment (DPIA) is being prepared for this
  pilot. A redacted summary will be made available on request from the
  Data Protection Officer.

## How is your data protected?

Expats is designed with privacy by default:

- Each session is isolated — your data is not shared with other users.
- Documents and any derived vector indices are deleted automatically when
  your session expires (default: 24 hours; confirm the configured value
  with `<INSTITUTION>`).
- Audit logs are retained for record-keeping and then permanently deleted
  (default: 1 year; confirm the configured value with `<INSTITUTION>`).
- No AI model is trained on your data.
- Where Expats calls an external AI provider, only the minimum data needed
  for the request is sent, and provider-side training on prompts is
  disabled.
- If an AI provider is located outside the EU/EEA, data is transferred
  under appropriate safeguards (Standard Contractual Clauses or
  equivalent).
- All data in transit is encrypted; data at rest is encrypted per
  `<INSTITUTION>`'s policy.

## Who is the data controller?

`<INSTITUTION>` is the data controller for personal data processed during
this pilot. Their contact details for data-protection matters are:

- Data Protection Officer: `<DPO_NAME>`
- Email: <`<DPO_EMAIL>`>
- Postal address: `<DPO_POSTAL_ADDRESS>`

## What is the lawful basis for processing your data?

Your **freely given, specific, informed and unambiguous consent**
(Article 6(1)(a) GDPR). You may withdraw your consent at any time.
Withdrawal does not affect the lawfulness of processing carried out before
withdrawal.

## Your data protection rights

Under GDPR you have the right to:

- **Access** the personal data we hold about you (Article 15).
- **Rectify** inaccurate or incomplete data (Article 16).
- **Erasure** ("right to be forgotten") (Article 17).
- **Restrict** processing of your data (Article 18).
- **Portability** of data you have provided (Article 20).
- **Object** to processing (Article 21).
- **Withdraw your consent** at any time without consequence (Article 7(3)).

You can exercise these rights by contacting <`<DPO_EMAIL>`>.

You may also download your own audit report at any time through the Expats
user interface.

## Right to lodge a complaint

If you believe your data has been processed in a way that does not comply
with the GDPR, you have the right to lodge a complaint with a supervisory
authority. The Belgian supervisory authority is the
**Gegevensbeschermingsautoriteit / Autorité de protection des données
(GBA/APD)**:

- Web: <https://www.dataprotectionauthority.be>
- Address: Rue de la Presse 35, 1000 Brussels, Belgium

If you are not based in Belgium, you may instead lodge a complaint with the
supervisory authority of your country of residence. See
<https://edpb.europa.eu/about-edpb/about-edpb/members_en>.

## How will the results be used?

- Aggregated, anonymised results may be published in academic papers,
  project reports, and presentations, including a demonstration at the
  GÉANT TNC 2026 conference and an online showcase.
- No individual participant will be identifiable in any publication.
- The Expats software itself is published as open source under the
  [PolyForm Noncommercial License 1.0.0](../LICENSE).

## Who has reviewed this study?

This study has been reviewed and approved by `<ETHICS_COMMITTEE_NAME>` of
`<INSTITUTION>` (reference: `<ETHICS_REF>`, date of approval:
`<APPROVAL_DATE>`).

## Who can I contact with questions?

- For questions about the study: `<PI_NAME>`, <`<PI_EMAIL>`>
- For data-protection questions: `<DPO_NAME>`, <`<DPO_EMAIL>`>
- For complaints: `<COMPLAINTS_CONTACT>`, or directly to the GBA/APD (see
  above)

## What happens next?

If, after reading this sheet, you are willing to take part, please read
and sign the accompanying **Informed Consent Form**
([`INFORMED_CONSENT_TEMPLATE.md`](INFORMED_CONSENT_TEMPLATE.md)).

Thank you for considering this study.

---

*Template version: 1.0 — based on the European Commission Horizon Europe
model Participant Information Sheet. Last updated: `<DATE>`.*
