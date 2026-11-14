# jev-config

Templates and four fixes for [jev-job-search](https://github.com/qbeka/jev-job-search), the part that fills and submits
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
With the new settings left empty, jev behaves exactly as upstream.

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

It also keeps the `focus` block when the dashboard saves the policy, and adds tests (`tests/focusOrder.test.ts`,
`tests/visaType.test.ts`).

```bash
cd ~/code/jev-job-search            # your clone of qbeka/jev-job-search
git apply --check /path/to/job-agents-kit/jev-config/jev-fixes.patch && git apply /path/to/job-agents-kit/jev-config/jev-fixes.patch
npx tsc --noEmit && npx vitest run
cp /path/to/job-agents-kit/jev-config/data/{profile.json,bank.json,policy.json,voice.local.md} data/   # only if you have none yet
```
