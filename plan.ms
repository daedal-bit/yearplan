# 📅 My Annual Five Goals Tracker: UI/UX Blueprint

This document details the UI/UX design for an annual goal tracking web application, prioritizing **minimalism, efficiency, and motivational feedback**.

## 🎨 Theme and Color Scheme: Vibrant Lime (Default)

This theme is chosen for its positive and encouraging visual feedback.

| Element | Color Code/Style (Reference) | Purpose |
| :--- | :--- | :--- |
| **Main Background** | Soft Light Gray/Off-White (`#F7F7F7`) | Clean, light, and provides visual breathing room. |
| **Card Background** | Pure White (`#FFFFFF`), with subtle rounded corners and soft shadow. | Highlights content, modern look. |
| **Primary Accent (Motivational)** | **Vibrant Lime Green (`#A7D129`)** | Used for **Progress Bars, '+1' Buttons, and 'On Track' status**. Signifies growth and success. |
| **Alert/Warning** | **Vibrant Orange (`#FF9800`)** | Used for the **'Behind Schedule'** status. |
| **Text Color** | Deep Dark Gray (`#333333`) | High contrast for readability. |

---

## 🏠 Main Dashboard Layout

**Core Principle:** Highest efficiency and lowest friction for data entry.

### 1. Layout Structure

* **Main Body:** **Five Goal Cards** displayed prominently (horizontal or grid layout).
* **Bottom Right:** **Floating Action Button (FAB) Group**, fixed to the corner of the viewport.

### 2. Goal Card Features

| Feature | Description | Function |
| :--- | :--- | :--- |
| **Progress Display** | Numerical progress, colored progress bar. | Immediate visual feedback on status. |
| **'In Track' Status** | Icon (🚀 for Ahead/On Track, ⚠️ for Behind) and color code. | System check against the goal's deadline. |
| **Immediate Update Button** | Action button (**'+1'** or **'Update'**), tailored to the task type. | The primary, fastest entry point (see *Core Interaction Logic*). |

### 3. Floating Action Button Group (FAB)

This fixed area provides quick access to major actions.

| Button | Shape/Style | Function |
| :--- | :--- | :--- |
| **Button 1 (Left)** | **Circular Button** (Icon like `📜` or `⚙️`) | **[View Logs / History]** entry point. |
| **Button 2 (Right)** | **Square Button** (Icon like `+` or `📝`) | **[Add New Task]** entry point. |

---

## 🚀 Core Interaction Logic: Instant Update

The functionality of the **'Update'** button on the Goal Card changes based on the task type selected during setup, optimizing for the fastest possible data entry.

| Task Type | Card Button Action | Interaction Flow | Efficiency Level |
| :--- | :--- | :--- | :--- |
| **1. Increment** (e.g., Reading, Running) | **[+1 Count]** Button (Prominently displayed) | **One-click** action, no pop-up. System immediately records '+1' and updates progress. | **Highest** (No modal required) |
| **2. Decrement** (e.g., Weight, Debt) | **[Record Latest Value]** Button | **Click** opens a **single-step modal** (only number input + date picker). | **Very High** (Single-step modal) |
| **3. Completion Rate** (e.g., Course, Project) | **[Update Progress %]** Button | **Click** opens a **single-step modal** (only slider/percentage input). | **Very High** (Single-step modal) |

---

## 🆕 Task Creation & Logging

### 1. Add New Task Flow (Single-Step Modal)

Clicking the **Square [Add New Task]** button opens a single modal to minimize friction.

| Field | UI Element | Purpose |
| :--- | :--- | :--- |
| **Name, Value, Unit** | Text/Number Inputs | Essential goal description. |
| **Task Type** | **Dropdown Selector** (Icons for Increment/Decrement/Completion) | **CRITICAL** for setting the card's update behavior. |
| **Start/End Date** | Date Pickers | Used to calculate the **'In Track' status** against the timeline. |

### 2. Log Page (History & Error Correction)

Accessed via the **Circular [View Logs]** button.

* **Data Display:** Shows a chronological list of all recorded actions (Time, Goal, Content).
* **Error Correction:** Each log entry must have easy access to **[Edit]** and **[Delete]** actions (e.g., via a three-dot menu).
    * **Edit:** Opens a modal to correct the recorded value or time.
    * **Delete:** Permanently removes the log entry (with confirmation), recalculating all progress metrics.