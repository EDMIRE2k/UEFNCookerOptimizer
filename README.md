# Cooker Optimizer Guide (UEFN Python Tool)

Cooker Optimizer is a Python tool designed to assist with resolving cook failures in Unreal Editor for Fortnite (UEFN), particularly "Cooker Out of Memory" issues.

This tool does not fix cook errors automatically. Instead, it provides a controlled workflow that allows you to cook your project in smaller batches by temporarily excluding selected actors from the cook process without needing to delete or rework them.

No assets are deleted or permanently modified. The tool only applies the hidden "Editor Only" flag to actors, which prevents them from being included in cooked builds.

<img width="1170" height="1274" alt="image" src="https://github.com/user-attachments/assets/42eccdf1-d55e-4edf-8ef0-09cfb7f4e8d0" />

---

## Installation

- Download the Python script  
- Open your project in UEFN  
- Enable Python scripting:  
  - Go to Project → Project Settings  
  - Enable Python Scripting  
- In the top toolbar, click Tools → Execute Python Script  
- Select and run the script  

The Cooker Optimizer window will open inside UEFN.

---

## How It Works

The tool allows you to:

- Scan your level to detect actors
- Select specific actor types (Blueprint Actors, Static Mesh Actors, Landscapes)
- Apply "Editor Only" flags to a percentage of actors
- Gradually reduce cook load on the server
- Iteratively restore full project cooking

This enables a staged cooking process instead of forcing the engine to process the entire map at once.

---

## Recommended Usage Workflow

### 1. Select Actor Types

Choose which actors to include in the scan.

Recommended:
- Blueprint Actors  
- Static Mesh Actors  

Landscapes are optional and should be used cautiously.

---

### 2. Run Scan

- Click Scan  
- The tool will analyze your level and display:
  - Eligible actors  
  - Already editor-only actors  
  - Not editor-only actors  
  - Breakdown by actor type  

You may need to resize the window to view all sections.

---

### 3. Choose an Exclusion Percentage

Select how many actors to exclude from cooking:

- 1/2 (50%)
- 1/3 (33%)
- 1/4 (25%)
- Custom percentage

When using custom values:
- Enter a number in the Custom % field  
- Click Custom  

A confirmation popup will appear before applying changes.

Note:
- UEFN may place popups behind the tool window  
- Move the window if needed to locate the prompt  

---

### 4. Apply Changes

- Confirm the operation  
- The tool will:
  - Mark selected actors as Editor Only  
  - Save the project  
  - Refresh the viewport  

This process may take several minutes. Temporary freezing may occur during viewport refresh.

---

### 5. Attempt a Cook (Launch Session)

After applying changes:

- Launch a session in UEFN  

If successful:
- The project has cooked using a reduced actor set  

---

## Iteration Strategy

### If Cook Succeeds

- Close the session  
- Either:
  - Reduce the exclusion percentage (e.g., from 50% to 25%), or  
  - Click Undo All to restore all actors  

Then:
- Launch again  

Because part of the project has already been cooked, subsequent cooks are often more stable.

---

### If Cook Fails

- Increase the exclusion percentage (e.g., 50% → 75%)  
- Apply again  
- Retry cooking  

Repeat until a successful cook is achieved.

---

### Final Goal

Gradually return to:

- 0% exclusion (Undo All)  
- Full project cooking without errors  

---

## Cooker Probability Section

At the bottom of the tool (may require resizing):

- A cook probability/debug section is available  
- This is experimental and not required  
- It helps estimate success likelihood based on previous attempts  

---

## Important Notes

- This tool does not fix underlying engine issues  
- It is a workaround to help manage cook load  
- Editor Only actors:
  - Will not appear in cooked builds  
  - May break references if misused so do not ship a map with any actors excluded  
- Always back up your project or use source control before using the tool  

---

## Conceptual Explanation

Think of the cook process like an oven:

- Trying to cook everything at once can overload the system and fail  
- This tool lets you cook the project in smaller batches  
- Once partial cooking succeeds, the remaining content becomes easier to process  

---

## Disclaimer

Use at your own risk.

This tool is not responsible for:
- Data loss  
- Broken references  
- Misuse of Editor Only flags  

Always verify results after each step.

---

## Credits

Created by BiomeForge  
Developed to work around current UEFN cooker limitations  
