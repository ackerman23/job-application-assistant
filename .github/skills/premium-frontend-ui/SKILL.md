---
name: premium-frontend-ui
description: 'Design and improve the Job Application Assistant frontend with a deliberate, polished visual system, accessible interactions, responsive Flask templates, and measured motion. Use when redesigning, styling, reviewing, or polishing the dashboard, forms, document controls, empty states, or other browser UI.'
---

# Premium Frontend UI for the Job Application Assistant

Create polished, high-trust interfaces that help users safely review personal application data. This workspace uses server-rendered Flask templates and CSS; improve those foundations before introducing client-side frameworks or animation libraries.

This project-tailored skill is informed by the external [Premium Frontend UI skill](https://github.com/github/awesome-copilot/blob/main/skills/premium-frontend-ui/SKILL.md). Product requirements, privacy, accessibility, and the existing architecture take priority.

## When to use

Use this skill for requests to:

- Redesign or visually polish the Flask dashboard or landing page.
- Improve profile, job-description, skill-selection, CV, or cover-letter workflows.
- Improve responsive layouts, typography, states, controls, or accessibility.
- Add restrained motion or feedback to user interactions.

## Product design principles

1. **Build trust first.** The product contains private profiles, job descriptions, and generated application materials. Make data handling, review steps, and export consequences clear.
2. **Make the workflow obvious.** The primary path is profile → job description → analysis → evidence review → document generation → review/download. Show the next meaningful action and avoid decorative distractions.
3. **Choose one visual direction.** Use a refined professional system with clear hierarchy, intentional spacing, and a limited color palette. Do not introduce generic gradients, glass effects, loaders, or animation merely for decoration.
4. **Preserve familiar conventions.** Forms, checkboxes, error messages, and downloads must behave predictably.
5. **Protect existing behavior.** Keep Flask routes, form names, submitted action values, template variables, and accessibility labels intact unless the change intentionally updates both server and tests.

## Workflow

### 1. Inspect before designing

- Read the target template, its inline or linked CSS, and the Flask route that supplies its data.
- Identify existing tokens, breakpoints, states, and semantic landmarks.
- Inspect the UI in a browser whenever practical before and after changes.
- Establish the most important user task, visual hierarchy, and responsive constraints.

### 2. Define a compact visual system

Before coding, decide and apply consistently:

- A small color system: neutral surfaces, strong readable text, one primary action color, and distinct success/warning/error colors.
- A type scale using `clamp()` only where it improves responsiveness; body text must remain at least 16px.
- A spacing, radius, border, and shadow scale.
- Clear visual treatment for panels, primary/secondary buttons, input fields, chips, alerts, disabled controls, and focus states.

Prefer CSS custom properties for reusable values. Use system fonts or a privacy-conscious web font choice; do not add a font download without a concrete benefit.

### 3. Improve information architecture

- Use semantic `header`, `main`, `nav`, `section`, headings, labels, and buttons.
- Group related controls and explain status labels such as `VERIFIED`, `TRANSFERABLE`, `FAMILIARITY`, and `MISSING` in plain language where needed.
- Keep primary actions visible without making secondary downloads compete for attention.
- Add useful empty, loading, success, and error states. Do not show a fake progress state for a synchronous server request.
- Ensure narrow screens stack content cleanly and keep controls easy to tap.

### 4. Add only purposeful motion

- Prefer short opacity and transform transitions for hover, focus, panel entrance, or status feedback.
- Animate only `transform` and `opacity`; do not animate layout properties such as `width`, `height`, `top`, or `margin`.
- Respect `prefers-reduced-motion: reduce` and keep the interface fully usable with motion disabled.
- Avoid scroll hijacking, custom cursors, preloaders, parallax, and heavy JavaScript unless the user explicitly asks and the benefit outweighs accessibility and maintenance costs.

### 5. Meet accessibility and quality requirements

- Maintain visible keyboard focus using `:focus-visible`.
- Use labels for every form control; do not rely on placeholders as labels.
- Preserve sufficient color contrast and never rely on color alone for status.
- Keep error feedback specific and connected to the relevant action or input.
- Confirm tab order, mobile layout, and at least one keyboard-only path.

### 6. Validate the result

- Run the relevant test suite after template or route changes.
- Check browser rendering at desktop and mobile widths when browser access is available.
- Confirm that forms still submit their original fields and action values.
- Confirm reduced-motion behavior for any new animation.
- Report the user-facing improvements and any intentional trade-offs.

## Implementation constraints

- Keep dependencies minimal. This Flask application should not add React, GSAP, Lenis, or a component framework for simple CSS improvements.
- Do not send user profile content or job text to new third-party frontend services.
- Do not weaken evidence labeling or the review-before-download workflow for visual convenience.
- Do not add visual noise that reduces readability of job requirements, evidence, or generated documents.
