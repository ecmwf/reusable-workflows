---
name: anemoi-architecture
description: Architectural boundaries of the anemoi package stack — in particular which heavy third-party libraries each package is allowed to depend on. Use when adding or moving a dependency in an anemoi package's pyproject.toml, when deciding where a piece of functionality belongs, when reviewing an import that crosses package boundaries, or when a change would make zarr or pytorch-lightning reachable from a package that must stay free of it.
---

# anemoi architecture

The anemoi stack is deliberately layered so that each package can be installed
and used on its own. The layering is enforced by dependencies: a package must
not require a heavy library that belongs to a different layer.

## Dependency boundaries

**zarr may only be a strong dependency of `anemoi-datasets`, and
pytorch-lightning may only be a strong dependency of `anemoi-training` — never
of `anemoi-models`.**

The reasoning behind each half of that rule:

- **zarr is a storage concern.** `anemoi-datasets` owns the on-disk dataset
  format, so it is the only package that may import zarr unconditionally.
  Anything downstream consumes datasets through the `anemoi-datasets` API
  instead of reaching for the store itself.
- **pytorch-lightning is a training-loop concern.** `anemoi-models` must stay a
  plain PyTorch model library, so that inference (`anemoi-inference`) and any
  other consumer can load and run a model without pulling in the training
  stack. Lightning modules, callbacks, trainers and loggers belong in
  `anemoi-training`.

## Applying it

- Adding one of these libraries to a package's `pyproject.toml` `dependencies`
  list is the thing to avoid. An **optional** extra, or a guarded import inside
  a narrow code path, is a different matter — but prefer moving the code to the
  package that owns the concern.
- A `pytorch_lightning` import appearing anywhere under `anemoi-models` is a
  layering violation, even if the dependency itself happens to be satisfied
  because `anemoi-training` is installed in the same environment.
- The same logic applies to any new heavy dependency: decide which layer owns
  the concern before deciding where the dependency goes.
