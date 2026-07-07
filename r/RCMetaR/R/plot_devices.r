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

rcmetar.open.plot_device <- function(outpath, size) {
    bg <- if (!is.null(size$bg)) size$bg else "white"
    ext <- rcmetar.plot.file.extension(outpath)
    if (identical(ext, "png")) {
        ragg::agg_png(filename=outpath, width=size$width, height=size$height, units="in", res=144, background=bg)
        return(invisible(ext))
    }
    if (identical(ext, "tif") || identical(ext, "tiff")) {
        ragg::agg_tiff(filename=outpath, width=size$width, height=size$height, units="in", res=300, background=bg)
        return(invisible(ext))
    }
    if (identical(ext, "svg") || identical(ext, "svgz")) {
        svglite::svglite(filename=outpath, width=size$width, height=size$height, bg=bg, standalone=TRUE, fix_text_size=TRUE)
        return(invisible(ext))
    }
    if (isTRUE(capabilities("cairo"))) {
        grDevices::cairo_pdf(filename=outpath, width=size$width, height=size$height, bg=bg)
    } else {
        grDevices::pdf(file=outpath, width=size$width, height=size$height, bg=bg)
    }
    invisible(ext)
}
