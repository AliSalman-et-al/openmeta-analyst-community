rcmetar.plot.file.extension <- function(outpath) {
    path <- tolower(as.character(outpath))
    if (grepl("[.]svg[.]gz$", path)) {
        return("svgz")
    }
    filename <- basename(path)
    ext <- sub("^.*[.]", "", filename)
    if (identical(ext, filename)) {
        return("pdf")
    }
    if (!nzchar(ext)) {
        return("pdf")
    }
    ext
}

rcmetar.plot.canonical_svg_path <- function(outpath) {
    path <- as.character(outpath)
    ext <- rcmetar.plot.file.extension(path)
    if (identical(ext, "svg") || identical(ext, "svgz")) {
        return(path)
    }

    filename <- basename(path)
    if (!grepl("[.]", filename)) {
        return(paste(path, ".svg", sep=""))
    }
    sub("[.][^.]*$", ".svg", path)
}

rcmetar.plot.scalar_path <- function(path) {
    if (is.null(path) || length(path) != 1 || is.na(path) ||
            !nzchar(as.character(path))) {
        return(NULL)
    }
    as.character(path)
}

rcmetar.plot.paths.equal <- function(left, right) {
    left <- rcmetar.plot.scalar_path(left)
    right <- rcmetar.plot.scalar_path(right)
    if (is.null(left) || is.null(right)) {
        return(FALSE)
    }
    identical(
        normalizePath(as.character(left), winslash="/", mustWork=FALSE),
        normalizePath(as.character(right), winslash="/", mustWork=FALSE)
    )
}

rcmetar.plot.display_path_for_bundle <- function(bundle, outpath, prefix) {
    params <- bundle$params
    if (is.null(params)) {
        return(NULL)
    }
    requested.outpath <- rcmetar.plot.scalar_path(
        params[[paste0(prefix, "_outpath")]]
    )
    display.path <- rcmetar.plot.scalar_path(
        params[[paste0(prefix, "_display_path")]]
    )
    if (!rcmetar.plot.paths.equal(requested.outpath, outpath) || is.null(display.path)) {
        return(NULL)
    }
    display.path
}

rcmetar.plot.export.dpi <- function(size) {
    if (!is.null(size$dpi) && is.finite(size$dpi) && size$dpi > 0) {
        return(size$dpi)
    }
    600
}

rcmetar.plot.pixel.size <- function(size) {
    dpi <- rcmetar.plot.export.dpi(size)
    c(
        width=max(1, ceiling(size$width * dpi)),
        height=max(1, ceiling(size$height * dpi))
    )
}

rcmetar.open.svg_device <- function(outpath, size) {
    bg <- if (!is.null(size$bg)) size$bg else "white"
    svglite::svglite(
        filename=outpath,
        width=size$width,
        height=size$height,
        bg=bg,
        standalone=TRUE,
        fix_text_size=TRUE
    )
    invisible(NULL)
}

rcmetar.svg.style.has.property <- function(node, property) {
    presentation <- xml2::xml_attr(node, property)
    if (!is.na(presentation)) {
        return(TRUE)
    }
    style <- xml2::xml_attr(node, "style")
    !is.na(style) && grepl(
        paste0("(^|;)[[:space:]]*", property, "[[:space:]]*:"),
        style,
        ignore.case=TRUE,
        perl=TRUE
    )
}

rcmetar.materialize.svg.property <- function(node, property, value) {
    if (!rcmetar.svg.style.has.property(node, property)) {
        xml2::xml_set_attr(node, property, value)
    }
    invisible(node)
}

rcmetar.sanitize.svg.xml <- function(svg) {
    # XML 1.0 permits tab, LF, and CR below U+0020, but not the other
    # control characters or references that graphics devices can occasionally
    # emit. Filter bytes first: an invalid control byte can survive in an R
    # character vector with an unknown encoding and evade a character regex.
    # Remove both forms before libxml2 expands character references.
    if (!is.raw(svg)) {
        svg <- charToRaw(svg)
    }
    bytes <- as.integer(svg)
    svg <- rawToChar(svg[!(bytes <= 8L | bytes %in% c(11L, 12L) | bytes >= 14L & bytes <= 31L)])
    svg <- gsub("[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F]", "", svg, perl=TRUE)
    svg <- gsub("&#0*(?:[0-8]|1[124-9]|2[0-9]|3[01]);", "", svg, perl=TRUE)
    gsub("&#[xX]0*(?:[0-8]|[bBcC]|[eEfF]|1[0-9a-fA-F]);", "", svg, perl=TRUE)
}

rcmetar.normalize.svglite.svg <- function(svg.path) {
    compressed <- grepl("[.]svgz$", tolower(svg.path))
    # svglite declares UTF-8. Reading through the native Windows code page can
    # corrupt non-ASCII labels before libxml2 sees them, especially when R's
    # requested UTF-8 locale is unavailable.
    input <- if (compressed) {
        gzfile(svg.path, open="rb")
    } else {
        file(svg.path, open="rb")
    }
    svg <- rawToChar(readBin(input, what="raw", n=100000000L))
    close(input)
    Encoding(svg) <- "bytes"
    svg <- rcmetar.sanitize.svg.xml(svg)

    document <- xml2::read_xml(charToRaw(svg), options="NOBLANKS")
    shapes <- xml2::xml_find_all(
        document,
        "//*[local-name()='g' and contains(concat(' ', normalize-space(@class), ' '), ' svglite ')]//*[local-name()='line' or local-name()='polyline' or local-name()='polygon' or local-name()='path' or local-name()='rect' or local-name()='circle']"
    )
    glyph.paths <- xml2::xml_find_all(
        document,
        "//*[local-name()='g' and contains(concat(' ', normalize-space(@class), ' '), ' svglite ')]//*[local-name()='g' and contains(concat(' ', normalize-space(@class), ' '), ' glyphgroup ')]//*[local-name()='path']"
    )
    if (length(glyph.paths) > 0) {
        shapes <- shapes[!(xml2::xml_path(shapes) %in% xml2::xml_path(glyph.paths))]
    }
    defaults <- c(
        fill="none",
        stroke="#000000",
        `stroke-linecap`="round",
        `stroke-linejoin`="round",
        `stroke-miterlimit`="10.00"
    )
    for (node in shapes) {
        for (property in names(defaults)) {
            rcmetar.materialize.svg.property(node, property, defaults[[property]])
        }
    }

    for (node in glyph.paths) {
        if (!rcmetar.svg.style.has.property(node, "fill")) {
            xml2::xml_set_attr(node, "fill", "inherit")
        }
        if (!rcmetar.svg.style.has.property(node, "stroke")) {
            xml2::xml_set_attr(node, "stroke", "none")
        }
    }

    normalized <- as.character(document)

    output <- if (compressed) gzfile(svg.path, open="wt") else file(svg.path, open="wt")
    writeLines(normalized, output, useBytes=TRUE)
    close(output)
    invisible(svg.path)
}

rcmetar.render.plot_svg <- function(svg.path, size, draw) {
    rcmetar.open.svg_device(svg.path, size)
    close.device <- TRUE
    on.exit({
        if (isTRUE(close.device)) {
            grDevices::dev.off()
        }
    }, add=TRUE)
    result <- draw()
    grDevices::dev.off()
    close.device <- FALSE
    rcmetar.normalize.svglite.svg(svg.path)
    invisible(result)
}

rcmetar.export.svg_render <- function(svg.path, outpath, size) {
    ext <- rcmetar.plot.file.extension(outpath)
    pixels <- rcmetar.plot.pixel.size(size)
    if (identical(ext, "png")) {
        rsvg::rsvg_png(svg.path, outpath, width=pixels[["width"]], height=pixels[["height"]])
        return(invisible(ext))
    }
    if (identical(ext, "tif") || identical(ext, "tiff")) {
        bitmap <- rsvg::rsvg(svg.path, width=pixels[["width"]], height=pixels[["height"]])
        if (length(dim(bitmap)) == 3 && dim(bitmap)[[3]] == 4) {
            bitmap <- bitmap[, , 1:3]
        }
        pixels <- dim(bitmap)
        grDevices::tiff(
            filename=outpath,
            width=pixels[[2]],
            height=pixels[[1]],
            units="px",
            res=rcmetar.plot.export.dpi(size),
            compression="lzw",
            bg="white"
        )
        tryCatch(
            grid::grid.raster(bitmap, interpolate=FALSE),
            finally=grDevices::dev.off()
        )
        return(invisible(ext))
    }
    rsvg::rsvg_pdf(svg.path, outpath)
    invisible(ext)
}

rcmetar.render.plot_file <- function(outpath, size, draw, display.path=NULL) {
    ext <- rcmetar.plot.file.extension(outpath)
    display.path <- rcmetar.plot.scalar_path(display.path)
    if (identical(ext, "svg") || identical(ext, "svgz")) {
        if (is.null(display.path)) {
            return(rcmetar.render.plot_svg(outpath, size, draw))
        }
        dir.create(dirname(display.path), recursive=TRUE, showWarnings=FALSE)
        result <- rcmetar.render.plot_svg(display.path, size, draw)
        if (!rcmetar.plot.paths.equal(display.path, outpath)) {
            if (!isTRUE(file.copy(display.path, outpath, overwrite=TRUE))) {
                stop("Could not copy the internal SVG display artifact to the requested output.", call.=FALSE)
            }
        }
        return(invisible(result))
    }

    keep.display <- !is.null(display.path)
    svg.path <- if (keep.display) as.character(display.path) else tempfile(
        pattern="rcmetar-plot-", fileext=".svg"
    )
    if (keep.display) {
        dir.create(dirname(svg.path), recursive=TRUE, showWarnings=FALSE)
    }
    if (!keep.display) {
        on.exit(unlink(svg.path), add=TRUE)
    }
    result <- rcmetar.render.plot_svg(svg.path, size, draw)
    rcmetar.export.svg_render(svg.path, outpath, size)
    invisible(result)
}
