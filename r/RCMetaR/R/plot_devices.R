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

rcmetar.plot.export.dpi <- function(size) {
    if (!is.null(size$dpi) && is.finite(size$dpi) && size$dpi > 0) {
        return(size$dpi)
    }
    300
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
        tiff::writeTIFF(bitmap, outpath, compression="LZW")
        return(invisible(ext))
    }
    rsvg::rsvg_pdf(svg.path, outpath)
    invisible(ext)
}

rcmetar.render.plot_file <- function(outpath, size, draw) {
    ext <- rcmetar.plot.file.extension(outpath)
    if (identical(ext, "svg") || identical(ext, "svgz")) {
        return(rcmetar.render.plot_svg(outpath, size, draw))
    }

    svg.path <- rcmetar.plot.canonical_svg_path(outpath)
    result <- rcmetar.render.plot_svg(svg.path, size, draw)
    rcmetar.export.svg_render(svg.path, outpath, size)
    invisible(result)
}
