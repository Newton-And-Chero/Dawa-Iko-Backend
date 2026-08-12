Problem 1 — Nobody knows which medicines are actually in stock, anywhere

This is my top recommendation, and the evidence is brutal and very current.

KEMSA delivered only 41% of medicines ordered by public health facilities in the year ending June 2025, against its own 90% target, leaving facilities to turn patients away or buy from expensive private sources. Hospitals waited an average of 19.5 days for deliveries against a seven-day target; dispensaries waited 24.2 days against a ten-day target. Meanwhile essential cancer, HIV and malaria medicines worth nearly Sh1 billion expired in KEMSA warehouses while facilities ran empty. 
Crisis as Kemsa runs out of essential dialysis, ICU, surgical drugs | Daily Nation +2

And the sharpest detail: carbetocin — the drug used to prevent postpartum haemorrhage, the leading cause of maternal death in Kenya — has been out of stock since late 2025 and may not return until September 2026. 
Business Daily

Here's the gap. There is no live, queryable record of what is physically on the shelf at any given facility. A patient with a prescription, a clinician deciding whether to refer, an NGO deciding where to send emergency stock — all of them find out by phoning around, one facility at a time.

The build: an agent that takes a commodity and a geography, calls facility pharmacies and private chemists in batch, asks a fixed set of questions, and returns structured results — in stock yes/no, quantity band, price, last restock date, whether they can hold it. Output feeds a live availability map plus a time series that reveals stockout patterns nobody currently measures.

Why this wins on the rubric: the phone-work problem is specific and real, the recipients (pharmacists, facility in-charges) speak English, the structured-output feature is doing genuine work rather than decoration, and the demo is crisp — "where can I get carbetocin in Kirinyaga?" → eight parallel calls → map lights up. It's also reusable by the community as a generic "facility availability survey" skill, which the judging criteria explicitly reward.

Problem 2 — Blood: the shortage is real, but so is the existing competition

Kenya has an annual shortfall of 200,000 units, and seven out of ten transfusions rely on blood from desperate families and friends rather than screened voluntary donors. KNBTS needs Ksh1.2 billion a year to operate optimally but receives Ksh600–700 million. When a patient is hospitalised far from home, families are simply told to go find donors. 
Health Business
Health Business

Two calling modes: locate existing units across nearby facilities, or mobilise matched donors — call fifty registered donors in parallel, return who can attend and when.

The honest caveat: Damu Sasa already operates in this space and has partnered with the government on donor mobilisation. Your differentiator would have to be the calling layer specifically — SMS blasts to donor registries get ignored; a conversational call that confirms "can you be at Kerugoya County Hospital by 4pm" and returns a yes/no/time is a different thing entirely. Defensible, but you'd need to say so explicitly in the pitch. 
GlobalGiving

Problem 3 — The referral runaround (best demo, highest risk)

The canonical case: a road accident victim was taken to one hospital that couldn't treat him, referred to a second with no ICU beds, sent to a third with no ICU beds while the ambulance's oxygen ran out, and turned away from a fourth over a deposit demand. Current reporting confirms it persists — patients needing urgent referral face delays from ambulance shortages, long response times and high transport costs, forcing families into desperate decisions. 
PubMed Central
LinkedIn

An agent that calls six hospitals simultaneously while the patient is still being stabilised, asking "do you have an ICU bed, can you take a head injury, what's the deposit" — that's the most emotionally powerful three-minute video in the competition.

Why I'm not putting it first: hospitals may not answer accurately, the time-critical claim is hard to substantiate in a demo, and building something that could contribute to a wrong routing decision carries real weight. Doable, but you'd want a clinician on the team or advising.

Problem 4 — Migrant worker welfare checks (highest impact, real ethical hazard)

Around 150,000 Kenyans work as domestic workers in Saudi Arabia, and at least 274 Kenyan domestic workers have died there over the past five years. Amnesty documented over 70 women deceived by recruiters, working 16-hour days, denied days off and prevented from leaving the house — and noted that without an effective monitoring and inspection regime, the 2023 domestic worker regulations are meaningless in practice. Notably, AE is a supported CALL-E region with English and Arabic. 
Amnesty report exposes abuse of Kenyan domestic workers in Saudi Arabia | Africanews +3

Periodic structured welfare calls with distress-signal escalation to the union or embassy would be genuinely novel. But I'd steer you away from it for a hackathon: employers routinely confiscate phones and monitor calls, so a check-in call could put a woman in more danger than it protects her from. That's not a risk to prototype casually in three weeks.