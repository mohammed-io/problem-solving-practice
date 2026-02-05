# Coaching Guide

**The philosophy and methodology behind this learning system.**

---

## The Philosophy

### Building Intuition, Not Memorizing Answers

The goal is **pattern recognition**, not solution recall. You want to reach a point where your brain automatically goes:

> "This looks like the GitHub incident - let me check connection pools first."

### How Hints Work

Each step **narrows the problem space** without giving the answer:

| Step | What It Does | Example |
|------|--------------|---------|
| 1 | Broad framework | "What method would you use?" |
| 2 | Points to area | "Check the database layer" |
| 3 | Specific component | "Look at connection pool settings" |
| 4 | Almost there | "max_connections is too low" |

### Why This Works

1. **Active recall** - You generate the answer, not receive it
2. **Metacognition** - You learn your own problem-solving patterns
3. **Progressive disclosure** - Builds confidence before deep dive

---

## Problem-Solving Frameworks

### RED Method (For Services)

When investigating a service problem, check:

| Metric | Question |
|--------|----------|
| **R**ate | Requests per second - is traffic normal? |
| **E**rrors | Error rate - is it elevated? |
| **D**uration | Latency (p50, p95, p99) - is it slow? |

### USE Method (For Resources)

When investigating resource problems:

| Resource | Question |
|----------|----------|
| **U**tilization | Is the resource busy? (CPU, memory, disk) |
| **S**aturation | Is there queued work? (load avg, conn pool) |
| **E**rrors | Is the resource throwing errors? |

### Five Whys (For Root Cause)

Keep asking "why" until you reach a systemic cause:

```
Problem: API is slow
1. Why slow? → Database queries taking long
2. Why slow? → Full table scans
3. Why scans? → No index on user_id
4. Why no index? → Query pattern changed, index not added
5. Why not added? → No process for reviewing query patterns

ROOT CAUSE: No index review process for schema changes
```

---

## Reading the Problems

### First Pass (problem.md only)

Read the scenario once. Then close it and ask:

1. **What do I know for certain?**
2. **What assumptions am I making?**
3. **What would I check first?**

Write down your answers before reading step-01.md.

### Subsequent Steps (step-N.md)

Each step should be read **only after you've tried to apply the previous step.**

The steps are designed to be:
- **Step 1-2**: Framework selection (RED? USE? Something else?)
- **Step 3-5**: Component identification
- **Step 6-8**: Specific mechanism
- **Step 9+**: Almost there, final nudge

### Solution (solution.md)

Read **only after you've solved it or given up.**

The solution includes:
- Root cause analysis
- What actually happened
- Trade-offs discussed
- Prevention strategies
- References to the real incident

---

## Common Traps

### Trap 1: Jumping to Conclusions

**Symptom**: "It's definitely X!"

**Reality**: You don't have enough data yet.

**Fix**: Use a framework (RED/USE) before hypothesizing.

### Trap 2: Ignoring the Timeline

**Symptom**: Focusing on current state, ignoring when things changed.

**Reality**: Incidents have a "before" and "after."

**Fix**: Always ask "What changed around the time this started?"

### Trap 3: Premature Optimization

**Symptom**: Solving for a problem that doesn't exist.

**Reality**: The actual issue is something else.

**Fix**: Verify your diagnosis before implementing fixes.

### Trap 4: Missing the Human Element

**Symptom**: "The system is broken, fix the system."

**Reality**: Humans caused this, humans need to fix it.

**Fix**: Consider communication, escalation, runbooks.

---

## When You're Stuck

### If You Have No Idea

1. **State what you know**: "I know X, Y, Z are happening."
2. **State what you don't know**: "I don't know why Z is happening."
3. **Pick a framework**: "I'll use RED method."
4. **Execute**: Gather the data the framework tells you to.

### If You Have a Hypothesis But Not Proof

1. **Write your hypothesis**: "I think X is causing Y because Z."
2. **Identify what would prove it**: "If I'm right, I should see A."
3. **Check for A**: Did you find it?

### If You've Tried Everything

1. **Re-read the problem** - You may have missed a detail
2. **Read the next step** - That's what they're there for
3. **Note what stumped you** - This is a learning gap

---

## Incident Response Behavior

### When You Discover an Incident

1. **Assess severity** (P0-P3)
2. **If P0/P1**: Page on-call immediately
3. **Post in #incidents** with the format:
   ```
   🔴 Incident: Brief description
   Severity: P0
   Investigating: @your-name
   ```
4. **Update every 15 minutes** even if no progress

### During the Incident

1. **One person typing in the terminal**
2. **One person updating chat**
3. **Everyone else looking at dashboards/logs**

Never have everyone doing the same thing.

### After the Incident

1. **Write the postmortem** within 48 hours
2. **Focus on systems, not blame**
3. **Identify action items** with owners
4. **Follow up** on action items

---

## Learning from Problems

### After Solving

Ask yourself:

1. **What framework helped most?** (RED? USE? Five Whys?)
2. **What clue did I miss initially?**
3. **What would I check first next time?**
4. **How could this have been prevented?**

### Note Your Patterns

Track:
- Which problem types you're good at
- Which problem types you struggle with
- Your common mistakes
- Frameworks that work for you

### Revisit Problems

Come back to problems in:
- **2 weeks** - See if you remember the approach
- **1 month** - Test if pattern recognition kicks in
- **3 months** - Should be automatic now

---

## Advanced Topics

### Trade-offs

Many problems have multiple valid solutions. The solution.md discusses:

- **Cost** of each approach
- **Complexity** introduced
- **Operational overhead**
- **Risk profile**
- **When to use each**

### "It Depends"

Senior engineers rarely give absolute answers. Instead:

- "It depends on your traffic pattern"
- "It depends on your consistency requirements"
- "It depends on your team's expertise"

This isn't hedging - it's acknowledging context.

### System Design vs. Troubleshooting

| Troubleshooting | System Design |
|-----------------|---------------|
| What's broken? | What should we build? |
| Fix the symptom | Prevent the problem |
| Reactive | Proactive |
| Minutes matter | Days/weeks matter |

Both skills are needed for senior roles.

---

## Final Advice

1. **Be patient** - Building intuition takes time
2. **Embrace confusion** - That's when learning happens
3. **Write it down** - External thinking builds clarity
4. **Teach others** - Explaining cements knowledge
5. **Stay curious** - The best engineers never stop asking "why?"

---

**Now go solve your first problem: `basic/incident-001-slow-api/`**
