# ai-friction-map

A diagnostic tool that parses Claude Code session logs and reveals where in your
codebase the model experiences friction — re-reads, edit churn, and re-evaluation
in its thinking blocks. Outputs an interactive HTML heatmap so you can see at a
glance which files are hardest for Claude Code to work with. Built for the
"Built with Opus 4.7" hackathon (April 2026).

## Install

pip install -e .

## Usage

# Retrospective scan — auto-detects the current project's sessions.
# Works from the project root OR any subdirectory.
cd ~/my-project
ai-friction-map scan
open report.html

# List sessions with recent activity (within the last 12 hours).
ai-friction-map active-sessions

# Analyze a specific session, by ID prefix or title substring.
ai-friction-map session 978c30c2
ai-friction-map session "migration order fix"
