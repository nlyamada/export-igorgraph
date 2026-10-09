#pragma rtGlobals=3

// EIG_Gallery.ipf  --  fidelity check for figures made by export_igor (verification tool)
//
// Needs ExportIgorGraphLoader.ipf to be open in the same experiment (it provides LoadPythonFigure and EIG_SelfTest).
//
//   RunGallery()
//     1. choose the gallery folder (the folder that contains the .h5 files made by gallery.py)
//     2. every figure is drawn through LoadPythonFigure, read back into igor_audit.txt, and saved as <name>_igor.png
//   Then send the whole gallery folder (zip) back.
//
//   EIG_RunGalleryAt(folderStr)
//     the same without a dialog (for automated runs). folderStr is a full path, e.g. "C:work:gallery".
//     When finished, EIG_done.txt is written in the folder (figures, failures, return code).

//-------------------------------------------//
// Run all figures
//-------------------------------------------//
Function RunGallery()

	NewPath/M="Select the gallery folder (it contains the .h5 files)."/O/Q EIG_GalPath
	if (V_flag != 0)
		Print "RunGallery: canceled."
		return -1
	endif
	return EIG_GalleryCore()
End

// No dialog: the folder is given as a full path. Writes EIG_done.txt at the end.
Function EIG_RunGalleryAt(folderStr)
	String folderStr

	Variable rc, refNum

	NewPath/O/Q/Z EIG_GalPath, folderStr
	if (V_flag != 0)
		Print "EIG_RunGalleryAt: the folder does not exist: " + folderStr
		return -1
	endif
	rc = EIG_GalleryCore()
	Open/Z/P=EIG_GalPath refNum as "EIG_done.txt"
	if (V_flag == 0)
		fprintf refNum, "DONE\t%d\r", rc
		Close refNum
	endif
	return rc
End

Function EIG_GalleryCore()

	Variable i, n, refNum, err, nFail
	String list, fname, gname, pngName

	if (EIG_SelfTest() != 0)
		Print "RunGallery: the allowlist self test failed. Stopped."
		return -1
	endif

	list = SortList(IndexedFile(EIG_GalPath, -1, ".h5"), ";", 0)
	n = ItemsInList(list)
	if (n == 0)
		Print "RunGallery: no .h5 files in the folder."
		return -1
	endif

	Open/Z/P=EIG_GalPath refNum as "igor_audit.txt"
	if (V_flag != 0)
		Print "RunGallery: cannot create igor_audit.txt in the gallery folder."
		return -1
	endif
	fprintf refNum, "# EIG gallery audit\r"
	fprintf refNum, "IGORVERSION\t%g\r", IgorVersion()
	fprintf refNum, "PLATFORM\t%s\r", IgorInfo(2)

	nFail = 0
	for (i = 0; i < n; i += 1)
		fname = StringFromList(i, list)
		gname = fname[0, strlen(fname) - 4]					// strip ".h5"
		err = LoadPythonFigure_exec(pathName="EIG_GalPath", h5Path=fname)
		fprintf refNum, "FIGURE\t%s\t%d\r", gname, err
		if (err != 0)
			nFail += 1
			fprintf refNum, "ENDFIGURE\r"
			continue
		endif
		DoUpdate/W=$gname
		EIG_AuditGraph(gname, refNum)
		pngName = gname + "_igor.png"
		SavePICT/O/Z/P=EIG_GalPath/E=-5/B=144/WIN=$gname as pngName
		Printf "RunGallery: %s done\r", gname
	endfor
	Close refNum

	Printf "RunGallery: %d figure(s), %d failed.\r", n, nFail
	Print "Results: igor_audit.txt and <name>_igor.png are in the gallery folder. Please send the folder (zip)."
	return nFail
End

//-------------------------------------------//
// Read a graph back (raw strings; the Python side parses them)
//-------------------------------------------//
Function EIG_AuditGraph(gname, refNum)
	String gname
	Variable refNum

	Variable i, n
	String traces, images, annots, t, info, rec, one

	traces = TraceNameList(gname, ";", 1)
	images = ImageNameList(gname, ";")
	EIG_WriteLine(refNum, "TRACES\t", traces)
	EIG_WriteLine(refNum, "IMAGES\t", images)

	GetWindow $gname wsize
	fprintf refNum, "WSIZE\t%g\t%g\t%g\t%g\r", V_left, V_top, V_right, V_bottom
	GetWindow $gname psize
	fprintf refNum, "PSIZE\t%g\t%g\t%g\t%g\r", V_left, V_top, V_right, V_bottom

	GetAxis/W=$gname/Q bottom
	fprintf refNum, "AXIS\tbottom\t%g\t%g\t%d\r", V_min, V_max, V_flag
	GetAxis/W=$gname/Q left
	fprintf refNum, "AXIS\tleft\t%g\t%g\t%d\r", V_min, V_max, V_flag

	n = ItemsInList(traces)
	for (i = 0; i < n; i += 1)
		t = StringFromList(i, traces)
		info = TraceInfo(gname, t, 0)
		EIG_WriteLine(refNum, "TRACEINFO\t" + t + "\t", EIG_Flat(info))
	endfor
	n = ItemsInList(images)
	for (i = 0; i < n; i += 1)
		t = StringFromList(i, images)
		info = ImageInfo(gname, t, 0)
		EIG_WriteLine(refNum, "IMAGEINFO\t" + t + "\t", EIG_Flat(info))
	endfor
	info = AxisInfo(gname, "bottom")
	EIG_WriteLine(refNum, "AXISINFO\tbottom\t", EIG_Flat(info))
	info = AxisInfo(gname, "left")
	EIG_WriteLine(refNum, "AXISINFO\tleft\t", EIG_Flat(info))

	annots = AnnotationList(gname)
	EIG_WriteLine(refNum, "ANNOTLIST\t", annots)
	n = ItemsInList(annots)
	for (i = 0; i < n; i += 1)
		t = StringFromList(i, annots)
		info = AnnotationInfo(gname, t)
		EIG_WriteLine(refNum, "ANNOTINFO\t" + t + "\t", EIG_Flat(info))
	endfor

	rec = WinRecreation(gname, 0)
	n = ItemsInList(rec, "\r")
	for (i = 0; i < n; i += 1)
		one = StringFromList(i, rec, "\r")
		EIG_WriteLine(refNum, "REC\t", one)
	endfor
	fprintf refNum, "ENDFIGURE\r"
	return 0
End

// Writes prefix + s + CR. Long strings are written in pieces (printf has a length limit).
Function EIG_WriteLine(refNum, prefix, s)
	Variable refNum
	String prefix, s

	Variable pos, e, n = strlen(s)
	fprintf refNum, "%s", prefix
	for (pos = 0; pos < n; pos += 800)
		e = min(pos + 799, n - 1)
		fprintf refNum, "%s", s[pos, e]
	endfor
	fprintf refNum, "\r"
End

// Replaces CR, LF and TAB by a space so that one record stays on one line.
Function/S EIG_Flat(s)
	String s

	s = ReplaceString("\r", s, " ")
	s = ReplaceString("\n", s, " ")
	s = ReplaceString("\t", s, " ")
	return s
End
