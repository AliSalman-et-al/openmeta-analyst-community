# Gate the first release on complete Qt6 evidence

The planned first public release date may slip and must not override the Native Qt6 Port acceptance gates. Release requires green native source and packaged evidence on Windows x64, macOS Intel x64, and macOS ARM64; working bundled R and rpy2 integration; semantically verified structured sample projects; Project Format Schema validation; and the strict `ty` and Qt6 verification lanes. Missing, waived, or platform-incomplete evidence blocks release rather than becoming post-release cleanup.
