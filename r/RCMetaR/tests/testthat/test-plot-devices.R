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
