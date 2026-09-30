"""Example 01: Create a project, optimize materials, query, and export.

This example demonstrates how to:
- create/open a CALM project
- add two bulks (LiF, Li2O) from bundled POSCAR files
- select and use an MLIP potential via the public Potential API
- optimize both bulks using the MLIP and persist optimized states to the project
- query project tables, retrieve saved objects, and export one as POSCAR

Requirements
- An MLIP provider must be available and registered with CALM's calculator
  registry (e.g., a GRACE provider). If a provider or the calculators extras
  are not present, this script will raise an informative error indicating the
  missing capability or environment dependency. Do not substitute EMT or any
  other fallback calculator: examples must exercise MLIP models.
"""

from __future__ import annotations

from pathlib import Path

from calm import Material, Potential, open_project

# The ten examples share one sibling project and one generated-artifact directory.
EXAMPLES_DIR = Path(__file__).resolve().parent
STRUCTURES_DIR = EXAMPLES_DIR / "Structures"
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --8<-- [start:tutorial-material-workflow]
# 1) Open a persistent project
project = open_project(PROJECT_DIR, summarize=True)

# 2) Load bundled example bulks (POSCARs live in examples/Structures)
lif = Material.from_file(STRUCTURES_DIR / "LiF.poscar", name="LiF")
li2o = Material.from_file(STRUCTURES_DIR / "Li2O.poscar", name="Li2O")

# Loaded materials
print("Loaded materials:")
# Persist the raw bulks so subsequent queries exercise project-backed tables.
# Examples must demonstrate typed retrieval from persistent project state.
project.add_material(lif, name="LiF_raw")
project.add_material(li2o, name="Li2O_raw")

# Display the persisted raw bulks using the objects returned by project.add_material
print()
# Display persisted raw bulks from the typed project collection.
# Use the collection.to_table() API, which returns a TableView that can be
# rendered in notebooks or scripts via .display().
project.materials().to_table(title="Project materials (after saving raw bulks)", max_width=200, max_col_width=30).display()

# 3) Choose a potential: an MLIP provider is required for this example.
# Construct the public Potential object and validate.
potential = Potential.grace("GRACE-1L-OMAT", device="cpu", quiet=True)
potential.validate()

# 4) Optimize bulks and save to project
print("Optimizing LiF...")
project.optimize_material(lif, potential=potential, fmax=0.05, relax_cell=True, name="LiF_opt")
print("Optimizing Li2O...")
project.optimize_material(li2o, potential=potential, fmax=0.05, relax_cell=True, name="Li2O_opt")
# --8<-- [end:tutorial-material-workflow]

# 5) Query saved materials and print a simple table
# Show persisted raw bulks and then the optimized bulks retrieved from the DB.
project.materials().to_table(title="Project materials (current)", max_width=200, max_col_width=30).display()

# --8<-- [start:tutorial-material-query-export]
# Re-query the persisted optimized records from the project and display them.
optimized = project.materials().where(kind="optimized")
optimized.to_table(
    title="Optimized bulks (persisted)",
    max_width=200,
    max_col_width=30,
).display()

# Compare typed structural metadata used to distinguish polymorphs.
optimized.to_table(
    view="characterization",
    title="Material characterization",
).display()
optimized.write_table(
    OUTPUT_DIR / "01_material_characterization.csv",
    view="characterization",
)

# Retrieve optimized material by label (basic-friendly)
lif_opt = project.material("LiF_opt")
print("Retrieved optimized material by label:")
print(lif_opt.summary())
print(lif_opt.characterize().summary())

# 7) Export persisted optimized structures to POSCAR format.
# Use the project-level export helper which returns written paths.
written = project.export_materials("LiF_opt", "Li2O_opt", directory=OUTPUT_DIR, format="vasp")
print(f"Exported {len(written)} structures to: {OUTPUT_DIR}")
# --8<-- [end:tutorial-material-query-export]

print("\nExample 01 completed. Project:", PROJECT_DIR)
print("Generated artifacts:", OUTPUT_DIR)
