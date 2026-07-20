# Why Manual Package Qualification #71 passed

**Status:** Evidence review, 21 July 2026  
**Question:** Why did Manual Package Qualification #71 pass while later native
macOS package qualifications failed?  
**Primary comparison:** run
[#71 / 29753220375](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29753220375)
at `7b79deec`, versus runs
[29771181657](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29771181657),
[29771670245](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29771670245),
[29772045777](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29772045777),
and [29772780843](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29772780843).

## Verdict

Run #71 was a real successful execution of the bytes it assembled, but it was
not a clean-build qualification. Both macOS jobs restored uv caches. At the
target-native `rpy2-rinterface` installation, uv reported only `Prepared 3
packages in 137ms` on ARM64 and did not report `Building rpy2-rinterface`.
The later run built that same native extension from source on both
architectures and immediately exposed loader-relative R edges that the
relocator did not support. Therefore the green run proved one cached native
artifact; it did not prove that the declared source-build procedure was
repeatable.

This is not explained by a runner-image change. The successful Intel job and
the first later failing Intel job both identify macOS 15.7.7 and runner image
`macos-15` version `20260715.0340.1` in their setup logs. Nor did a source
change introduce the first failure: commit `7b79deec` changed only Windows
qualification files, and the macOS build/signing files were unchanged through
the first later failure.

The later failures are a sequence, not one recurring failure:

1. A clean `rpy2-rinterface` build exposed `@loader_path/libR.dylib`.
2. Handling that one filename exposed `@loader_path/libRblas.0.dylib`.
3. General handling of loader-relative R libraries allowed both architectures
   to pass the rpy2 build, relocation, and import proof, after which the jobs
   reached the already-fragile app-bundle signing boundary.
4. The signing runs then failed on code-bundle ownership/verification, first
   by verifying the app launcher as standalone code and then by verifying the
   outer app without preserving the launcher's seal context. Those are later,
   distinct defects which #71 happened not to expose with its cached bundle
   composition.

The correct conclusion is not “#71 was fake” and not “GitHub randomly broke
the build.” The correct conclusion is: **#71 was a valid but cache-conditioned
sample, and the qualification design made a broader clean-build claim than
its evidence supported.**

## Evidence

### 1. The workflow explicitly restored uv's build cache

The exact workflow at `7b79deec` configured `astral-sh/setup-uv` with
`enable-cache: true`; the package script then requested
`uv pip install --reinstall --no-binary rpy2-rinterface`, but did not use
`--no-cache` or `--refresh-package`. See the exact
[`package-target.yml`](https://github.com/AliSalman-et-al/rc-metastudio/blob/7b79deec4414949cb88730bb9caf23504fb2177c/.github/workflows/package-target.yml)
and
[`build-macos-package.sh`](https://github.com/AliSalman-et-al/rc-metastudio/blob/7b79deec4414949cb88730bb9caf23504fb2177c/scripts/build-macos-package.sh).

That distinction matters. `--reinstall` controls installation into the target
environment; it does not prove that the wheel was rebuilt. uv's own cache
documentation says that wheels built from source are deliberately retained in
CI because rebuilding extension modules is expensive. See
[uv's official cache documentation](https://docs.astral.sh/uv/concepts/cache/#caching-in-continuous-integration).

### 2. #71 reused the native artifact; the later run compiled it

In #71, the
[ARM64 job](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29753220375/job/88389005091)
logged a setup-uv cache hit and later `Prepared 3 packages in 137ms`; there is
no `Building rpy2-rinterface` line at that installation. Its Intel peer also
restored the uv cache and passed. The workflow's separate Qt SDK cache also
hit, but that is not the differentiator: later failures restored the same Qt
SDK cache and failed specifically while loading the newly built rpy2 bridge.

Four hours later, both jobs in
[run 29771181657](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29771181657)
logged `Building rpy2-rinterface==3.6.6` and `Built
rpy2-rinterface==3.6.6` (6.81 seconds on ARM64 and 5.84 seconds on Intel).
Both then failed importing `_rinterface_cffi_api.abi3.so` because dyld could
not find `@loader_path/libR.dylib`: see the
[ARM64 job](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29771181657/job/88449485158)
and
[Intel job](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29771181657/job/88449485270).

This is direct evidence that the two runs did not exercise the same native
build product even though they requested the same locked package version.

### 3. Runner drift does not explain the first divergence

The #71
[Intel setup log](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29753220375/job/88389005313)
and the later failing
[Intel setup log](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29771181657/job/88449485270)
both report:

- macOS 15.7.7 (`24G720`);
- runner image `macos-15`, version `20260715.0340.1`;
- hosted-compute provisioner version `20260707.563`.

The later ARM64 job identifies the corresponding `macos-15-arm64`
`20260715.0234.1` image. There is no evidence of an image rollover between
the successful run and the first failure.

### 4. The one-name patch exposed the next loader-relative dependency

Commit
[`337f5cb3`](https://github.com/AliSalman-et-al/rc-metastudio/commit/337f5cb354931f70e6a94604ccd639360448d1b6)
added relocation for only `@loader_path/libR.dylib`. The next clean ARM64
job built rpy2 again and failed on
`@loader_path/libRblas.0.dylib`, as shown by
[job 88451123247](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29771670245/job/88451123247).
That progression falsifies the assumption that only `libR.dylib` needed
special treatment.

Commit
[`fc4bb487`](https://github.com/AliSalman-et-al/rc-metastudio/commit/fc4bb4878f999f8789ea2390e4ee22e01b44dd82)
generalized relocation to `@loader_path/*.dylib`. In the following
[qualification run](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29772045777),
both macOS jobs again built rpy2 from source, passed the former import point,
completed PyInstaller assembly, and reached signing. That is strong causal
evidence that the cache had concealed an incomplete loader-edge classifier.

### 5. #71 contained a warning that should have prevented a broad signing claim

PyInstaller's own signing attempt in #71 warned that the app's main executable
or `Info.plist` was not a regular file, identifying `R.framework` as the
subcomponent, and said the bundle would need manual signing. The custom
inside-out signing pass subsequently reported success, so #71 was entitled to
claim that its particular app passed that pass. It was not entitled to erase
the warning from the risk model or treat one bundle layout as proof that all
freshly built native inputs had the same signing ownership.

Once the clean-built bridge was accepted, run
[29772045777](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29772045777)
failed after signing the launcher and nested bundles when it attempted to
verify `Contents/MacOS/RCMetaStudio` independently. Commit
[`a42827c`](https://github.com/AliSalman-et-al/rc-metastudio/commit/a42827c978a649628e24bf2bd330925dbe623d3d)
changed signing ownership, and
[run 29772780843](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29772780843)
then advanced to outer-app verification before failing. These are observed
stage transitions. It would be speculation to attribute every signing detail
solely to the rpy2 cache without comparing the emitted bundles byte-for-byte.

## What #71 actually proved

It proved, for one cached dependency state at exact commit `7b79deec`, that:

- native Intel and ARM64 jobs completed;
- their assembled and archived applications passed the then-current runtime
  and evidence checks;
- the custom ad-hoc signing pass accepted those particular bundle trees.

It did **not** prove:

- that `rpy2-rinterface` could be rebuilt from its locked source against the
  staged R framework;
- that every dependency emitted by that source build was relocatable;
- that a cache miss produced a bundle equivalent to the cache-hit bundle;
- repeatability across two independent clean builds; or
- that the PyInstaller signing warning was harmless for every possible bundle
  composition.

## Durable qualification rule

Package qualification should separate acceleration from proof:

1. Keep the Qt SDK cache; its content is explicitly keyed by Qt version and
   target and was not implicated by the logs.
2. For the native rpy2 proof lane, force a source build without reusing uv's
   built-wheel cache (for example, use a dedicated empty `UV_CACHE_DIR` or the
   appropriate uv refresh/no-cache control), and retain `Building`/`Built`
   evidence plus the resulting wheel or bridge hash and `otool -L` inventory.
3. Run the exact package twice: one clean-build qualification and, optionally,
   one cache-reuse reproducibility check. The cached result must not substitute
   for the clean result.
4. Treat PyInstaller's failed automatic signing as an explicit expected
   handoff only if the custom signer subsequently proves the outer app seal,
   nested bundles, launcher, archive round trip, and launch. Preserve the
   warning in evidence rather than allowing the final green badge to hide it.
5. Do not close issues #342–#344 from #71. Require a green exact-head clean
   Intel/ARM64 matrix and qualified downloadable artifacts from the protected
   release commit.

## Confidence and remaining uncertainty

The cache explanation for the initial `libR`/`libRblas` failures is **high
confidence**: the logs directly distinguish reuse from compilation, and the
general loader-path fix moves both jobs past that exact boundary. The precise
mechanism by which bundle composition changes the later codesign behavior is
**not yet fully proven**; the logs establish a distinct later signing defect,
not its complete binary-level causation. That distinction should be retained
until the succeeding clean run and its bundle inventories are available.
