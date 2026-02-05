# Problem Solving Coach - AGENTS.md

**This file defines the structure and conventions for adding new problems to the problem-solving-coach.**

---

## Directory Structure

```
problem-solving-coach/
├── learning-materials/
│   ├── basic/           # Beginner incidents (1 file per problem)
│   ├── intermediate/     # Intermediate incidents
│   ├── advanced/         # Complex incidents
│   └── real-world/       # Real-world incidents
└── each-problem-directory/
    ├── problem.md        # Required: Incident description with frontmatter
    ├── step-01.md        # Optional: First hint/guidance
    ├── step-02.md        # Optional: Second hint
    ├── step-03.md        # Optional: Third hint (rare)
    ├── solution.md       # Required: Complete solution
    └── lab/              # Optional: Hands-on coding environment
        ├── README.md
        └── (starter files)
```

---

## File Format Specifications

### problem.md (Required)

**Must include YAML frontmatter:**

```yaml
---
name: "Incident Name"
category: "basic|intermediate|advanced|real-world"
difficulty: "beginner|intermediate|advanced"
time: "XX minutes"          # Estimated completion time
services: ["service1"]      # Optional: Services involved
concepts: ["concept1"]      # Optional: Key concepts
---

# Incident Title

**Story-based scenario description**

## Context

Provide background on what system is failing and why it matters.

## The Incident

Describe the observable symptoms:
- What users are experiencing
- What monitoring/alerts show
- Timeline of events (if relevant)

## Requirements

Clear list of what needs to be fixed:
1. Fix X
2. Restore Y
3. Optimize Z

## Constraints

Limitations on the solution:
- Can't change X
- Must maintain Y
- Budget/time constraints

## Your Task

Specific actionable steps for the learner.

## Verification

How to check the solution works.
```

### step-*.md (Optional)

```markdown
# Step N: Title

**Guidance for this step of the investigation**

## Analysis

Explain what to look at, what questions to ask.

## Your Task

Specific action items for this step.

## Quick Check

5 questions to test understanding, each with parenthetical answer:

1. Question text? (The answer - hidden in parentheses)

2. Another question? (Another answer)
```

### solution.md (Required)

```markdown
# Solution: Incident Name

## Root Cause

What was actually wrong.

## The Fix

Code or configuration changes needed.

## Why This Happened

Educational context about the underlying issue.

## Prevention

How to avoid this in the future.
```

### lab/ (Optional)

Used for hands-on coding exercises:
- Must have `README.md` with setup instructions
- Starter files with `TODO` comments
- Verification script if applicable

---

## Frontmatter Fields

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `name` | Yes | string | Human-readable incident name |
| `category` | Yes | basic, intermediate, advanced, real-world | Difficulty category |
| `difficulty` | Yes | beginner, intermediate, advanced | Specific difficulty level |
| `time` | Yes | "XX minutes" or "XX hours" | Estimated completion time |
| `services` | No | [string] | Services or technologies involved |
| `concepts` | No | [string] | Key concepts taught |

---

## Quick Check Format

Each step file should end with exactly 5 questions:

```markdown
## Quick Check

Test your understanding:

1. What is X? (X is the answer - concise explanation)

2. How does Y work? (Y works by...)

3. When would you use Z? (Use Z when...)

4. What's the difference between A and B? (A does this while B does that...)

5. Why is C important? (C is important because...)
```

**Rules:**
- Exactly 5 questions per step
- Answers in parentheses immediately after each question
- Answers should be concise but complete
- Questions should test the key concepts from that step

---

## Adding New Problems

1. **Choose category** based on complexity
2. **Create directory** in appropriate category folder
3. **Write problem.md** with complete frontmatter
4. **Create step-*.md files** (1-3 steps typically)
5. **Write solution.md** with complete explanation
6. **Add lab/** if hands-on coding is needed
7. **Update main.py** to include new problem (if using web interface)

---

## Naming Conventions

- **Directories**: `incident-XXX-name` (3-digit pad number, kebab-case name)
- **Files**: Lowercase with hyphens, use suffix for clarity
- **Examples**:
  - `incident-001-cache-stampede/`
  - `incident-045-race-condition/`

---

## Content Guidelines

### Problem Quality
- **Realistic**: Based on actual production scenarios
- **Teachable**: Has clear learning objectives
- **Self-contained**: Can be solved without external help
- **Verifiable**: Clear success criteria

### Step Quality
- **Progressive**: Each step builds on previous
- **Guided**: Don't just give the answer, guide discovery
- **Scaffolded**: Provide enough structure for success

### Solution Quality
- **Complete**: Fully working code/configuration
- **Explained**: Why this fixes the issue
- **Educational**: What to learn from this

---

## Testing New Problems

Before marking complete:
1. Follow your own steps from problem.md
2. Verify solution.md actually works
3. Check Quick Check answers are accurate
4. Test lab files if present
5. Run in web interface to verify display

---

## What NOT To Do

- ❌ Create problems with multiple valid solutions (unless that's the point)
- ❌ Skip frontmatter in problem.md
- ❌ Write vague Quick Check questions
- ❌ Create lab/ for theoretical/conceptual problems
- ❌ Include answers in problem.md
- ❌ Use AI-generated content without human review
