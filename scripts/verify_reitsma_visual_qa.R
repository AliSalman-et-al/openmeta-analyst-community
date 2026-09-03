#!/usr/bin/env Rscript

# Maintained Reitsma visual release evidence. The harness exercises the
# package's analysis/rendering entry points and checks SVG semantics, not merely
# that a file happened to be written.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) > 1L) stop("usage: verify_reitsma_visual_qa.R [OUTPUT_ROOT]", call.=FALSE)
root <- if (length(args) == 1L) normalizePath(args[[1]], winslash="/", mustWork=FALSE) else
  file.path(tempdir(), "rcmetastudio-reitsma-visual-qa")
dir.create(root, recursive=TRUE, showWarnings=FALSE)

qa_load_reitsma <- function() {
  repo <- normalizePath(getwd(), winslash="/", mustWork=TRUE)
  mode <- tolower(Sys.getenv("RCMS_REITSMA_VISUAL_QA_MODE", "source"))
  if (!mode %in% c("source", "installed"))
    stop("RCMS_REITSMA_VISUAL_QA_MODE must be 'source' or 'installed'.", call.=FALSE)

  if (identical(mode, "installed")) {
    installed.library <- Sys.getenv("RCMS_REITSMA_VISUAL_QA_LIBRARY", "")
    if (!nzchar(installed.library) || !dir.exists(installed.library))
      stop("installed-package mode requires RCMS_REITSMA_VISUAL_QA_LIBRARY to name an existing R library.", call.=FALSE)
    installed.library <- normalizePath(installed.library, winslash="/", mustWork=TRUE)
    workspace.source <- normalizePath(file.path(repo, "r", "RCMetaR"), winslash="/", mustWork=FALSE)
    .libPaths(c(installed.library, .libPaths()))
    if (!requireNamespace("RCMetaR", quietly=TRUE))
      stop("installed-package mode could not load RCMetaR from RCMS_REITSMA_VISUAL_QA_LIBRARY.", call.=FALSE)
    package.path <- normalizePath(find.package("RCMetaR"), winslash="/", mustWork=TRUE)
    if (!startsWith(package.path, paste0(installed.library, "/")))
      stop("installed-package mode resolved RCMetaR outside RCMS_REITSMA_VISUAL_QA_LIBRARY.", call.=FALSE)
    if (identical(package.path, workspace.source) || startsWith(package.path, paste0(workspace.source, "/")))
      stop("installed-package mode resolved RCMetaR from the workspace source tree.", call.=FALSE)
    suppressPackageStartupMessages(library(RCMetaR))
    return(invisible(package.path))
  }

  # Source mode is intentionally retained for a developer running this file
  # directly.  The integrated release verifier always selects installed mode.
  library.roots <- c(file.path(repo, "build", "current-r-library"), file.path(repo, "build", "current-package", "dist", "RCMetaStudio", "R", "library"))
  .libPaths(c(library.roots[dir.exists(library.roots)], .libPaths()))
  if (requireNamespace("pkgload", quietly=TRUE)) {
    pkgload::load_all(file.path(repo, "r", "RCMetaR"), quiet=TRUE)
    return(invisible(file.path(repo, "r", "RCMetaR")))
  }
  if (requireNamespace("RCMetaR", quietly=TRUE)) {
    suppressPackageStartupMessages(library(RCMetaR))
    return(invisible(find.package("RCMetaR")))
  }
  stop("RCMetaR or pkgload is required for source-mode Reitsma visual QA.", call.=FALSE)
}

qa_svg_semantics <- function(path, labels=character(), colors=character(), min.graphics=8L) {
  if (!file.exists(path) || is.na(file.info(path)$size) || file.info(path)$size < 1000)
    stop("Missing or empty Reitsma SVG: ", path, call.=FALSE)
  if (!requireNamespace("xml2", quietly=TRUE)) stop("xml2 is required for SVG QA.", call.=FALSE)
  doc <- tryCatch(xml2::read_xml(path), error=function(e) stop("Invalid SVG XML: ", conditionMessage(e), call.=FALSE))
  if (!identical(xml2::xml_name(xml2::xml_root(doc)), "svg")) stop("SVG root element is not <svg>.", call.=FALSE)
  raw <- paste(readLines(path, encoding="UTF-8", warn=FALSE), collapse="\n")
  if (grepl("NaN|Inf|r_tmp|plotdata", raw, ignore.case=TRUE)) stop("Internal/invalid value leaked into SVG: ", path, call.=FALSE)
  text <- paste(xml2::xml_text(xml2::xml_find_all(doc, ".//*[local-name()='text']"), trim=TRUE), collapse=" ")
  missing <- labels[!vapply(labels, grepl, logical(1), x=text, fixed=TRUE)]
  if (length(missing)) stop("SVG is missing semantic labels (", paste(missing, collapse=", "), "): ", path, call.=FALSE)
  graphics <- xml2::xml_find_all(doc, ".//*[local-name()='path' or local-name()='polyline' or local-name()='polygon' or local-name()='circle' or local-name()='line']")
  if (length(graphics) < min.graphics) stop("SVG has too little drawable geometry: ", path, call.=FALSE)
  raw.colors <- toupper(raw)
  missing.colors <- colors[!vapply(toupper(colors), grepl, logical(1), x=raw.colors, fixed=TRUE)]
  if (length(missing.colors)) stop("SVG is missing edited style color(s): ", paste(missing.colors, collapse=", "), call.=FALSE)
  invisible(TRUE)
}

qa_binary_export <- function(path, extension) {
  if (!file.exists(path) || is.na(file.info(path)$size) || file.info(path)$size < 1000)
    stop("Missing or empty Reitsma ", extension, " export: ", path, call.=FALSE)
  bytes <- readBin(path, what="raw", n=8L)
  hex <- paste(sprintf("%02x", as.integer(bytes)), collapse="")
  expected <- switch(tolower(extension),
    png="89504e470d0a1a0a",
    pdf="255044462d",
    tiff=c("49492a00", "4d4d002a"),
    stop("Unsupported Reitsma export extension: ", extension, call.=FALSE))
  if (tolower(extension) == "tiff") {
    if (!any(startsWith(hex, expected))) stop("Invalid TIFF signature: ", path, call.=FALSE)
  } else if (!startsWith(hex, expected)) {
    stop("Invalid ", extension, " signature: ", path, call.=FALSE)
  }
  invisible(TRUE)
}

qa_sha256 <- function(path) {
  if (!requireNamespace("digest", quietly=TRUE))
    stop("digest is required for deterministic visual QA hashes.", call.=FALSE)
  digest::digest(path, algo="sha256", file=TRUE)
}

qa_pdf_contract <- function(path) {
  # PDF producers may embed timestamps and producer metadata.  Keep the
  # release gate semantic: validate the signature, one-page contract, and
  # complete trailer without comparing unstable metadata bytes.
  raw <- readBin(path, what="raw", n=100000000L)
  bytes <- as.integer(raw)
  ascii <- bytes[(bytes %in% c(9L, 10L, 13L)) | (bytes >= 32L & bytes <= 126L)]
  text <- rawToChar(as.raw(ascii))
  pages <- gregexpr("/Type[[:space:]]*/Page([^s]|$)", text, perl=TRUE)[[1L]]
  page.count <- if (identical(pages, -1L)) 0L else length(pages)
  list(
    signature = rawToChar(raw[seq_len(min(length(raw), 5L))]),
    pages = page.count,
    has_xref_or_xref_stream = grepl("startxref", text, fixed=TRUE),
    has_eof = grepl("%%EOF", text, fixed=TRUE),
    min_bytes = 1000L
  )
}

qa_normalized_descriptor <- function(descriptor) {
  list(
    plot_kind=as.character(descriptor$plot_kind),
    editable=isTRUE(descriptor$editable),
    styleable=isTRUE(descriptor$styleable),
    composition=as.character(descriptor$composition),
    regenerator=as.character(descriptor$regenerator)
  )
}

qa_descriptor <- function(descriptor, expected.kind) {
  required <- c("plot_kind", "editable", "styleable", "composition", "regenerator")
  if (!is.list(descriptor) || !setequal(names(descriptor), required))
    stop("Reitsma plot descriptor is not normalized: unexpected fields.", call.=FALSE)
  if (!identical(as.character(descriptor$plot_kind), expected.kind) ||
      !is.logical(descriptor$editable) || length(descriptor$editable) != 1L ||
      !is.logical(descriptor$styleable) || length(descriptor$styleable) != 1L ||
      !identical(as.character(descriptor$composition), "single") ||
      !identical(as.character(descriptor$regenerator), if (expected.kind == "sroc") "sroc" else "forest"))
    stop("Reitsma plot descriptor has invalid normalized values.", call.=FALSE)
  qa_normalized_descriptor(descriptor)
}

qa_data <- function() {
  new("DiagnosticData", TP=c(19,8,41,5,45,8,21,33), FN=c(10,2,12,2,32,2,9,11),
    TN=c(81,13,49,18,165,32,72,91), FP=c(1,9,1,1,58,6,5,7), study.names=letters[seq_len(8)])
}

qa_regression_data <- function() {
  data <- qa_data()
  data@covariates <- list(
    new("CovariateValues", cov.name="quality", cov.vals=c("A","A","B","B","A","B","A","B"), cov.type="factor", ref.var="A"),
    new("CovariateValues", cov.name="threshold", cov.vals=seq_len(8), cov.type="continuous", ref.var="")
  )
  data
}

qa_row <- function(case, family, kind, workflow, scenario, image, error=NA_character_) {
  bytes <- if (file.exists(image)) file.info(image)$size else NA_real_
  extension <- tolower(tools::file_ext(image))
  deterministic <- extension %in% c("svg", "svgz", "png", "tif", "tiff")
  sha256 <- if (deterministic && file.exists(image)) qa_sha256(image) else NA_character_
  pdf.contract <- if (identical(extension, "pdf") && file.exists(image)) {
    paste(jsonlite::toJSON(qa_pdf_contract(image), auto_unbox=TRUE, null="null"), collapse="")
  } else NA_character_
  data.frame(case=case, family=family, kind=kind, workflow=workflow, style="default", scenario=scenario,
             extension=extension,
             image=normalizePath(image, winslash="/", mustWork=FALSE), bytes=bytes,
             sha256=sha256, pdf_contract=pdf.contract, error=error, stringsAsFactors=FALSE)
}

qa_render <- function(output.root=root) {
  root <- normalizePath(output.root, winslash="/", mustWork=FALSE)
  dir.create(root, recursive=TRUE, showWarnings=FALSE)
  qa_load_reitsma()
  data <- qa_data(); rows <- list()
  add <- function(case, family, kind, workflow, scenario, image, labels, colors=character(), draw=function(path) invisible(path)) {
    err <- NA_character_
    tryCatch({
      draw(image)
      extension <- tolower(tools::file_ext(image))
      if (extension %in% c("svg", "svgz")) qa_svg_semantics(image, labels, colors)
      else {
        qa_binary_export(image, extension)
        if (identical(extension, "pdf")) {
          contract <- qa_pdf_contract(image)
          if (!identical(contract$pages, 1L) || !isTRUE(contract$has_xref_or_xref_stream) || !isTRUE(contract$has_eof))
            stop("PDF failed the normalized one-page/trailer contract: ", image, call.=FALSE)
        }
      }
    }, error=function(e) err <<- conditionMessage(e))
    rows[[length(rows)+1L]] <<- qa_row(case, family, kind, workflow, scenario, image, err)
  }
  add_export_set <- function(case, family, kind, workflow, scenario, stem, labels, colors=character(), draw=function(path) invisible(path)) {
    for (extension in c("svg", "png", "pdf", "tiff")) {
      add(paste0(case, "__", extension), family, kind, workflow, scenario,
          file.path(root, paste0(stem, ".", extension)), labels, colors, draw)
    }
  }

  fit <- mada::reitsma(data.frame(TP=data@TP, FN=data@FN, FP=data@FP, TN=data@TN), correction=.5, correction.control="all", method="reml")
  standard.plot <- rcmetar.regenerate.plot.data(data, fit, list(conf.level=95, fp_show_legend=TRUE, fp_show_confidence=TRUE, fp_show_prediction=TRUE))
  descriptor.contract <- list(schema_version=1L, descriptors=list())
  descriptor.result <- RCMetaR:::diagnostic.reitsma(data, list(create.plot=TRUE, conf.level=95, digits=3,
      fp_outpath=file.path(root, "descriptor-sroc.svg")))
  descriptor.contract$descriptors$sroc <- qa_descriptor(descriptor.result$plot_capabilities[["SROC"]], "sroc")
  qa_svg_semantics(file.path(root, "descriptor-sroc.svg"), c("False Positive Rate", "Sensitivity"))
  add_export_set("sroc__default", "sroc", "diagnostic", "standard", "default", "sroc-default",
      c("False Positive Rate", "Sensitivity", "Normalized partial SROC AUC"), character(), function(path) rcmetar.draw.sroc.plot(standard.plot, path))
  edited.plot <- standard.plot
  edited.plot$style$curve.color <- "#c0392b"; edited.plot$style$confidence.color <- "#1f7a8c"; edited.plot$style$prediction.color <- "#6a4c93"
  edited.plot$style$xlabel <- "False-positive rate (edited)"; edited.plot$style$ylabel <- "Sensitivity (edited)"
  edited.plot$style$show.legend <- TRUE; edited.plot$style$marker.area <- "sample-size"; edited.plot$style$show.marker.legend <- TRUE
  add("sroc__edited", "sroc", "diagnostic", "standard", "edited", file.path(root, "sroc-edited.svg"),
      c("False-positive rate (edited)", "Sensitivity (edited)", "Normalized partial SROC AUC"),
      c("#c0392b", "#1f7a8c", "#6a4c93"), function(path) rcmetar.draw.sroc.plot(edited.plot, path))

  reg <- qa_regression_data()
  cases <- list(continuous=list(covariates=reg@covariates[2], label="continuous"), categorical=list(covariates=reg@covariates[1], label="categorical"), multiple=list(covariates=reg@covariates, label="multiple"))
  for (entry in cases) {
    reg_data <- reg; reg_data@covariates <- entry$covariates
    params <- list(create.plot=TRUE, fp_outpath=file.path(root, paste0("coeff-", entry$label, ".svg")), estimator="REML", conf.level=95, correction.policy="All studies if any zero exists", adjust=.5)
    result <- RCMetaR:::diagnostic.reitsma.meta.regression(reg_data, params)
    normalized <- lapply(result$plot_capabilities, qa_descriptor, expected.kind="forest")
    descriptor.contract$descriptors$coefficient_forest <- normalized[[1L]]
    for (title in names(result$images)) {
      image <- unname(result$images[[title]])
      labels <- if (entry$label %in% c("categorical", "multiple")) c("quality = A (reference)", "Odds ratio") else c("Odds ratio")
      add(paste0("coefficients__", entry$label, "__", tolower(gsub(" ", "-", title))), "coefficient_forest", "diagnostic", "meta-regression", entry$label, image, labels)
    }
    if (entry$label == "categorical") for (scale in c("Sensitivity", "Specificity")) {
      plot.data <- rcmetar.regenerate.plot.data(reg_data, result$res, list(conf.level=95, reitsma.coefficient.scale=scale, reitsma.moderator.coding=list(quality=list(type="factor", levels=c("A","B"), reference="A")), fp_accent_color=if (scale == "Sensitivity") "#c0392b" else "#1f7a8c", fp_point_size_multiplier=1.4))
      image <- file.path(root, paste0("coeff-edited-", tolower(scale), ".svg"))
      add(paste0("coefficients__edited-", tolower(scale)), "coefficient_forest", "diagnostic", "meta-regression", "edited", image, c("quality = A (reference)", "Odds ratio"), c(if (scale == "Sensitivity") "#c0392b" else "#1f7a8c"), function(path) rcmetar.draw.forest.plot(plot.data, path))
      if (identical(scale, "Sensitivity")) {
        default.plot.data <- rcmetar.regenerate.plot.data(reg_data, result$res, list(conf.level=95,
          reitsma.coefficient.scale=scale, reitsma.moderator.coding=list(quality=list(
            type="factor", levels=c("A","B"), reference="A")), fp_point_size_multiplier=1.4))
        add_export_set("coefficients__default-export", "coefficient_forest", "diagnostic", "meta-regression", "default", "coeff-default-sensitivity",
          c("quality = A (reference)", "Odds ratio"), character(), function(path) rcmetar.draw.forest.plot(default.plot.data, path))
        add_export_set("coefficients__edited-export", "coefficient_forest", "diagnostic", "meta-regression", "edited", "coeff-edited-sensitivity",
          c("quality = A (reference)", "Odds ratio"), "#c0392b", function(path) rcmetar.draw.forest.plot(plot.data, path))
      }
    }
  }
  manifest <- do.call(rbind, rows)
  if (!requireNamespace("jsonlite", quietly=TRUE)) stop("jsonlite is required for descriptor QA.", call.=FALSE)
  jsonlite::write_json(descriptor.contract, file.path(root, "descriptor-contract.json"), auto_unbox=TRUE, pretty=TRUE)
  utils::write.csv(manifest, file.path(root, "manifest.csv"), row.names=FALSE)
  if (any(!is.na(manifest$error) & nzchar(manifest$error))) stop("Reitsma visual QA failures.", call.=FALSE)
  manifest
}

if (identical(Sys.getenv("RCMS_REITSMA_VISUAL_QA_LOAD_ONLY", ""), "1")) {
  loaded.from <- qa_load_reitsma()
  cat("RCMS_REITSMA_VISUAL_QA_LOADED_FROM", loaded.from, "\n")
  quit(save="no", status=0L)
}

if (sys.nframe() == 0L) {
  manifest <- qa_render()
  cat("REITSMA VISUAL QA", nrow(manifest), "SEMANTIC CASES OK\n")
}
