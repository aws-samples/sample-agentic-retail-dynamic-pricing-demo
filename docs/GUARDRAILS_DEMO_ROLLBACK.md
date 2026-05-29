# Guardrails Demo Simulation — Rollback Guide

## What Was Changed

### Files Modified
1. **`frontend/dashboard/src/App.tsx`** — Added "Guardrails Enforcement" section to SimulationsTab with 6 demo cards + `GuardrailDemoCard` component
2. **`cdk/stacks/api_handlers.py`** — Added `/guardrails/demo` POST endpoint with Lambda integration

### Files Created
1. **`backend/api_handlers/guardrails_demo.py`** — New Lambda handler for guardrails demo endpoint
2. **`frontend/dashboard/src/App.tsx.backup`** — Backup of original App.tsx

## How to Revert

### Option 1: Restore from backup file
```bash
cp frontend/dashboard/src/App.tsx.backup frontend/dashboard/src/App.tsx
rm backend/api_handlers/guardrails_demo.py
git checkout -- cdk/stacks/api_handlers.py
```

### Option 2: Git revert (if committed)
```bash
git log --oneline -5  # Find the commit hash
git revert <commit-hash>
```

### Option 3: Manual removal
1. In `App.tsx`: Remove the `{/* Guardrails Enforcement Scenarios */}` section (~50 lines) from `SimulationsTab`
2. In `App.tsx`: Remove the `GuardrailDemoCard` function component (~100 lines)
3. In `cdk/stacks/api_handlers.py`: Remove the guardrails demo resource block (~15 lines)
4. Delete `backend/api_handlers/guardrails_demo.py`

## Verification After Rollback
```bash
# Frontend builds
cd frontend/dashboard && npm run build

# CDK synthesizes
cd cdk && npx cdk synth

# Tests pass
PYTHONPATH=. pytest tests/ -v
```
