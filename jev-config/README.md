# jev-config

Templates and a patch for [jev-job-search](https://github.com/qbeka/jev-job-search), the part that fills and submits
application forms. Everything here is empty or generic: fill it in for yourself.

| File | Goes to (in your jev-job-search folder) |
|---|---|
| `data/profile.json` | `data/profile.json`: who you are. Every field the forms may ask for. |
| `data/bank.json` | `data/bank.json`: your drafts for common questions (why this company, about yourself...). |
| `data/voice.local.md` | `data/voice.local.md`: how your written answers sound. |
| `data/policy.json` | `data/policy.json`: the daily run's limits, where and what to apply to, employers never to apply to, and the focus order. |
| `jev-fixes.patch` | applied with `git apply` (below). |

The templates are empty, so jev's checks will reject them until you fill them in: run `npx jev doctor` to see what is missing.
Put every name from `../profile/never-apply.md` into `excludeEmployers` in `data/policy.json` too, so jev never applies there.

## jev-fixes.patch

Made against upstream commit `4442778` (release 1.7.0); it also applies cleanly to `bda2daf` (main on 13 Nov 2026).

**The biggest change: jev submits nothing on its own.** With the patch, every run prepares: it fills and checks each
form, leaves each ready one open in jev's Chrome window, and lists it as waiting for your approval. A form is sent only
when you approve it by id. Everything else (focus and visa settings) behaves exactly as upstream while left empty.

0. **Approve each form (the default).** `policy.json` gets `"mode": "prepare"` (also the default with no policy file,
   or one that cannot be read). In prepare mode `daily`, `apply --submit` (with ids or `--count`) and `resume --submit`
   submit nothing: each ready form waits with the status "ready for your approval" (`npx jev status`). Read the open
   form, then send only the ones you approve: `npx jev submit <id>` (in Claude Code: `/daily approve <id>`; `/daily
   approve` alone only lists them). Waiting forms count towards the day's target (at most 10 open at once) and are
   closed after 30 hours. `"mode": "send"`, or `npx jev daily --send` for one run, restores upstream's sending.

1. **Focus ordering.** `policy.json` gets a `focus` block: `titles`, `seasonFirst`, `seasonLast`, `placesFirst`, `placesThen`
   (case-insensitive patterns, matched at a word start). Queued jobs are taken by season (first, none, last), then titles in
   focus, then place (first, then, rest), then score.
2. **Score floor.** `focus.minScore`: a role in focus, or one whose season ranks first, needs only this lower fit score.
   The rating tends to score these lower than a generic role, so under one floor the run never reached them.
3. **Visa-type gate.** `profile.json` `workAuthorization` gets `visaType` (your visa or work-permit type, as you would write
   it), `visaTypeNames` (how a form's options may name it) and `neverVisaTypes` (types never to give). An answer naming a
   type from `neverVisaTypes` and not yours is refused and left for you.
4. **Writer rule.** With `visaType` set, the writer and the form mapper are told your type, never to pick a forbidden one,
   to leave the field for you when no option names yours, and that in `authorizedWithSponsorshipLater` countries you are
   currently authorized (so a current-authorization question there is Yes).

It also keeps the `focus` block and the `mode` when the dashboard saves the policy, and adds tests
(`tests/focusOrder.test.ts`, `tests/visaType.test.ts`, `tests/prepareApply.test.ts`, `tests/prepareDaily.test.ts`).

```bash
git clone https://github.com/qbeka/jev-job-search.git ~/jev-job-search   # needs Node.js 22 or newer
cd ~/jev-job-search
npm install
git apply --check ~/job-agents-kit/jev-config/jev-fixes.patch && git apply ~/job-agents-kit/jev-config/jev-fixes.patch
npx tsc --noEmit && npx vitest run  # everything should pass
cp -n ~/job-agents-kit/jev-config/data/{profile.json,bank.json,policy.json,voice.local.md} data/   # -n: never overwrites yours
# now fill in data/profile.json (workAuthorization and the visa fields included), bank.json and voice.local.md,
# and put your resume where profile.json's resume.path says; npx jev doctor lists what is still missing
npx jev doctor
npx jev apply --dry --count 3       # rehearse: read every answer
npx jev apply --submit --count 2    # prepares 2 forms, submits nothing
npx jev status                      # lists them as ready for your approval
npx jev submit <id>                 # sends only the one you approved
```
