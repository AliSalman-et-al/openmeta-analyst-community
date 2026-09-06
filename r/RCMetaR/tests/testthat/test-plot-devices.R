test_that("svglite shape defaults are materialized for QtSvg compatibility", {
  svg.path <- tempfile(fileext = ".svg")
  writeLines(c(
    "<svg xmlns='http://www.w3.org/2000/svg'>",
    "<g class='svglite'>",
    "<line id='line' x1='0' y1='0' x2='1' y2='1'/>",
    "<polyline id='explicit' points='0,0 1,1' style='stroke: #2f5597;'/>",
    "<polygon id='polygon' points='0,0 1,0 1,1'/>",
    "<path id='path' d='M 0 0 L 1 1'/>",
    "<rect id='rect' x='0' y='0' width='1' height='1'/>",
    "<circle id='circle' cx='0' cy='0' r='1'/>",
    "<g class='glyphgroup'><path id='glyph' d='M 0 0 L 1 1'/></g>",
    "</g></svg>"
  ), svg.path)

  rcmetar.normalize.svglite.svg(svg.path)
  first.pass <- readLines(svg.path, warn = FALSE)
  rcmetar.normalize.svglite.svg(svg.path)
  expect_identical(readLines(svg.path, warn = FALSE), first.pass)

  document <- xml2::read_xml(svg.path)
  for (id in c("line", "polygon", "path", "rect", "circle")) {
    node <- xml2::xml_find_first(document, paste0("//*[@id='", id, "']"))
    expect_equal(xml2::xml_attr(node, "fill"), "none")
    expect_equal(xml2::xml_attr(node, "stroke"), "#000000")
    expect_equal(xml2::xml_attr(node, "stroke-linecap"), "round")
    expect_equal(xml2::xml_attr(node, "stroke-linejoin"), "round")
    expect_equal(xml2::xml_attr(node, "stroke-miterlimit"), "10.00")
  }
  explicit <- xml2::xml_find_first(document, "//*[@id='explicit']")
  expect_match(xml2::xml_attr(explicit, "style"), "stroke: #2f5597", fixed = TRUE)
  expect_true(is.na(xml2::xml_attr(explicit, "stroke")))
  glyph <- xml2::xml_find_first(document, "//*[@id='glyph']")
  expect_equal(xml2::xml_attr(glyph, "fill"), "inherit")
  expect_equal(xml2::xml_attr(glyph, "stroke"), "none")
})

test_that("normalized svglite defaults support compressed SVG artifacts", {
  svgz.path <- tempfile(fileext = ".svgz")
  connection <- gzfile(svgz.path, open = "wt")
  writeLines("<svg xmlns='http://www.w3.org/2000/svg'><g class='svglite'><line x1='0' y1='0' x2='1' y2='1'/></g></svg>", connection)
  close(connection)

  rcmetar.normalize.svglite.svg(svgz.path)

  connection <- gzfile(svgz.path, open = "rt")
  document <- xml2::read_xml(paste(readLines(connection, warn = FALSE), collapse = "\n"))
  close(connection)
  line <- xml2::xml_find_first(document, "//*[local-name()='line']")
  expect_equal(xml2::xml_attr(line, "stroke"), "#000000")
})

test_that("SVG normalization removes XML 1.0-invalid control characters", {
  svg.path <- tempfile(fileext = ".svg")
  bytes <- c(
    charToRaw("<svg xmlns='http://www.w3.org/2000/svg'><text>bad"),
    as.raw(4),
    charToRaw("&#x4;char</text></svg>")
  )
  writeBin(bytes, svg.path)

  expect_silent(rcmetar.normalize.svglite.svg(svg.path))
  normalized.bytes <- readBin(svg.path, what = "raw", n = file.info(svg.path)$size)
  expect_false(any(as.integer(normalized.bytes) == 4L))
  expect_silent(xml2::read_xml(svg.path))
  expect_match(paste(readLines(svg.path, warn = FALSE), collapse = ""), "badchar", fixed = TRUE)
})

test_that("SVG normalization reads declared UTF-8 independently of the native locale", {
  svg.path <- tempfile(fileext = ".svg")
  svg <- paste0(
    "<?xml version='1.0' encoding='UTF-8'?>",
    "<svg xmlns='http://www.w3.org/2000/svg'><text>",
    "Between-study τ² and I²",
    "</text></svg>"
  )
  writeBin(charToRaw(enc2utf8(svg)), svg.path)

  expect_silent(rcmetar.normalize.svglite.svg(svg.path))
  document <- xml2::read_xml(svg.path)
  expect_equal(xml2::xml_text(xml2::xml_find_first(document, "//*[local-name()='text']")),
               "Between-study τ² and I²")
})

test_that("TIFF exports retain the requested publication resolution", {
  svg.path <- tempfile(fileext=".svg")
  tiff.path <- tempfile(fileext=".tiff")
  writeLines(c(
    "<svg xmlns='http://www.w3.org/2000/svg' width='1in' height='.5in'>",
    "<rect width='1' height='.5' fill='white'/>",
    "</svg>"
  ), svg.path)

  rcmetar.export.svg_render(
    svg.path,
    tiff.path,
    list(width=1, height=.5, dpi=300)
  )

  image <- tiff::readTIFF(tiff.path)
  expect_equal(unname(dim(image)[1:2]), c(150L, 300L))

  bytes <- readBin(tiff.path, what="raw", n=file.info(tiff.path)$size)
  endian <- if (rawToChar(bytes[1:2]) == "II") "little" else "big"
  read.integer <- function(offset, size) {
    readBin(bytes[(offset + 1):(offset + size)], "integer", n=1, size=size,
            endian=endian, signed=if (size <= 2) FALSE else TRUE)
  }
  ifd.offset <- read.integer(4, 4)
  entries <- read.integer(ifd.offset, 2)
  tags <- list()
  for (index in seq_len(entries)) {
    entry.offset <- ifd.offset + 2 + (index - 1) * 12
    tag <- read.integer(entry.offset, 2)
    type <- read.integer(entry.offset + 2, 2)
    count <- read.integer(entry.offset + 4, 4)
    if (type == 5L && count == 1L && tag %in% c(282L, 283L)) {
      value.offset <- read.integer(entry.offset + 8, 4)
      numerator <- read.integer(value.offset, 4)
      denominator <- read.integer(value.offset + 4, 4)
      tags[[as.character(tag)]] <- numerator / denominator
    } else if (type == 3L && count == 1L && tag == 296L) {
      tags[[as.character(tag)]] <- read.integer(entry.offset + 8, 2)
    }
  }
  expect_equal(tags[["282"]], 300)
  expect_equal(tags[["283"]], 300)
  expect_equal(tags[["296"]], 2)
})
