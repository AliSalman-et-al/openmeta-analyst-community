# R integration-kit delivery contract

RC MetaStudio packages R and rpy2 as one target-native, content-addressed
integration kit. The supported targets are Windows x64, macOS Intel x64, and
macOS Apple Silicon arm64; the arm64 R 4.6.1 kit has a macOS 14 minimum.

`scripts/r_integration_kit.py` owns the shared build, verification, and
consumption schema. A kit contains the private official CRAN R runtime, its
private locked package library, the target-native rpy2 API bridge, installed
package identities, licenses/source provenance, an authenticated uv cache for
the exact `uv.lock`, and complete native import or load-command records. Its
canonical manifest digest and per-file hashes make
mutation or ABI fallback a verification failure.

The reusable kit-producer workflow runs natively on each target before package
assembly. It downloads and verifies the official R installer/pkg, installs the
staged runtime directly from that authenticated artifact, and verifies the
exact rpy2 3.6.7 umbrella, rinterface 3.6.6, and robjects 3.6.5 distribution
set. It retains every exact PPM binary archive, records HSROC and RCMetaR source
archives and build logs, and embeds the exact HSROC, RCMetaR, rpy2,
rpy2-rinterface, and rpy2-robjects source archives. Each split rpy2 sdist has
independent license-file hashes. The producer uses a clean dedicated uv cache
populated from the exact lock, builds the API bridge, profiles/relocates macOS R,
then promotes the content-addressed kit as an immutable workflow artifact.
The package job downloads that exact artifact before toolchain setup, verifies
its digest, every member, and the consumer `uv.lock`, then performs an offline,
locked uv sync exclusively against the kit-carried cache. It passes the
same manifest digest to a small offline assembler. Release assembly has no package-resolution,
package-install, RCMetaR/HSROC build, or rpy2 fallback path. The explicit
producer scripts are the development entry points when a new kit is needed.

`sources.json` contains HTTPS URLs and SHA-256 identities for the signed R
artifact, every PPM binary, both source exceptions, and the rpy2 sdist plus
toolchain/build-log and license records. `native-dependencies.json` recursively
resolves normal and delayed PE imports and Mach-O load commands to unique
kit-owned hashes or narrow OS allowlists. External X11, `/opt/R`, Homebrew,
Conda, user, build, missing, ambiguous, wrong-architecture, or duplicate-R
identities are rejected.
The final Windows deployment inspector repeats normal and delay-import closure
over every packaged EXE, DLL, and PYD. The MSVC runtimes are not system
exceptions and must resolve to one authenticated app-local file.

Frozen startup does not consult ambient R or user libraries. It establishes
the app-relative R home and library, restricted DLL/path policy, isolated R
startup files, and `RPY2_CFFI_MODE=API` before importing rpy2. Runtime evidence
must report the actually loaded API mode. Packaging rejects
`_rinterface_cffi_abi`, inspectors require one target-native API extension,
and every logical R operation passes through the process-wide serialized,
main-thread gateway.

Before signing, assembly records the source-kit to relocated-app mapping.
After native signing it records final hashes and signing identities, reseals
the outer macOS bundle, and binds the derivation record into deployment and
qualification evidence. Frozen bootstrap validates the kit and derivation
before rpy2 import, initializes once on the main thread, disables ambient R
and startup files, applies the restricted Windows DLL policy, fixes
`LC_NUMERIC=C`, and uses writable home/temp directories outside the bundle.
Signed Windows release finalization additionally requires Authenticode status,
signer certificate subject/thumbprint, and timestamp certificate
subject/thumbprint evidence bound to the exact API bridge and `R.dll` paths and
hashes. Unsigned qualification may still finalize without that signed-release
evidence, but signed release finalization rejects an unsigned identity.

The macOS kit retains the official framework topology and the researched
non-X11 product profile. `bin/R` is a script, `bin/exec/R` is the thin native R
executable, and `lib/libR.dylib` is the canonical embedded-library Mach-O.
The API bridge is relocated against the app-owned framework before the final
inside-out signing inventory is sealed.
