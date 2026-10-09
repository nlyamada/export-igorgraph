"""export_igorgraph: turn a matplotlib figure into an Igor Pro graph.

    import export_igorgraph                      # import before calling contour()/contourf()
    from export_igorgraph import export_igor
    report = export_igor(fig, "out", "fig1")     # -> out/fig1.h5 ; in Igor: LoadPythonFigure()

Importing this package wraps the public ``Axes.contour`` / ``Axes.contourf`` so that the original (X, Y, Z) of a contour set
is remembered (matplotlib itself does not keep Z).  Use ``uninstall_contour_capture()`` to remove the wrapper.
"""

from .mpl_to_igor import (  # noqa: F401
    STYLE_DEFAULT,
    STYLE_IMAGE,
    ExportReport,
    check_style_file,
    export_igor,
    install_contour_capture,
    uninstall_contour_capture,
)

__version__ = "0.1.0"
__all__ = [
    "export_igor",
    "check_style_file",
    "ExportReport",
    "STYLE_DEFAULT",
    "STYLE_IMAGE",
    "install_contour_capture",
    "uninstall_contour_capture",
    "__version__",
]
