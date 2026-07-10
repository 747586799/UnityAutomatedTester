---
name: "web-design-guidelines"
description: "Audits UI code against Vercel's Web Interface Guidelines for design and accessibility compliance. Invoke when user asks for UI/code review, design audit, or accessibility check of web interfaces."
---

# Web Interface Guidelines

Review files for compliance with Vercel's Web Interface Guidelines.

## How It Works

1. Fetch the latest guidelines from the source URL below
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

Fetch fresh guidelines before each review:
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
