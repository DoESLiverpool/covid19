# python stl file tools
import re
import struct
import math

###########################################################################
def TriangleNormal(x0, y0, z0, x1, y1, z1, x2, y2, z2):
    # calculate facet normal
    v01 = (x1 - x0, y1 - y0, z1 - z0)
    v02 = (x2 - x0, y2 - y0, z2 - z0)
    n = (v01[1] * v02[2] - v01[2] * v02[1], v01[2] * v02[0] - v01[0] * v02[2], v01[0] * v02[1] - v01[1] * v02[0])
    lnsq = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    if lnsq > 0.0:
        ln = math.sqrt(lnsq)
        return (n[0] / ln, n[1] / ln, n[2] / ln)


###################################################################################
#
#
class FacetTrans:
    ''' apply a workplane when loading a file into fssurf '''
    def __init__(self, workplane, fssurf):
        self.wp = workplane
        self.fssurf = fssurf

    def ApplyWorkplane(self, p):
        pn = []
        for i in range(4):
            pn.append(self.wp[i][0] * p[0] + self.wp[i][1] * p[1] + self.wp[i][2] * p[2] + self.wp[i][3])
        if pn[-1] != 1.0:
            return (pn[0] / pn[-1], pn[1] / pn[-1], pn[2] / pn[-1])
        return (pn[0], pn[1], pn[2])

    def PushTriangle(self, x0, y0, z0, x1, y1, z1, x2, y2, z2):
        p0 = self.ApplyWorkplane((x0, y0, z0))
        p1 = self.ApplyWorkplane((x1, y1, z1))
        p2 = self.ApplyWorkplane((x2, y2, z2))
        self.fssurf.PushTriangle(p0[0], p0[1], p0[2], p1[0], p1[1], p1[2], p2[0], p2[1], p2[2])




###########################################################################
class reader:
    def __init__(self, fn = None, anglerange = None):
        self.fn = fn
        self.filterangle = anglerange
        if self.fn:
            self.isascii = False
            try:
                fl = open(self.fn, "r")
                self.isascii = self.IsAscii(fl)
                fl.close()
            except IOError as e:
                print(e)
                pass

        self.little_endian = (struct.unpack("<f", struct.pack("@f", 140919.00))[0] == 140919.00)

#        print "computer is little endian: ", self.little_endian
#        print "file is ascii: ", self.isascii

        self.nfacets = 0
        self.ndegenerate = 0

        self.mr = MeasureBoundingBox()
        self.colors = [ ]
        self.filtercolors = [ ]


    def IsAscii(self, fl):
        l = fl.readline(1024)
        isascii = l[:5] == "solid" and (len(l) == 5 or (re.search("[^A-Za-z0-9\,\.\/\;\:\'\"\+\-\s\r\n<>\(\)\_]", l[6:]) == None)) # some files say 'solid' but are binary files, we try to find a non alphanumerical character in the rest to the first line
        fl.seek(0)
        return isascii

    def ReadVertex(self, l):
        l = l.replace(",", ".") # Catia writes ASCII STL with , as decimal point
        if re.search("facet", l) or re.search("outer", l) or re.search("endloop", l) or re.search("endfacet", l):
            return

        vertex = re.search("vertex\s*([\d\-+\.EeDd]+)\s*([\d\-+\.EeDd]+)\s*([\d\-+\.EeDd]+)", l)

        if vertex:
            return (float(vertex.group(1)), float(vertex.group(2)), float(vertex.group(3)))



    def BinaryReadFacets(self, fl, fs = None):
        # 80 bytes of header
        hdr = fl.read(80).decode("utf-16")

        # color information for magics stl files, look for "COLOR=" in header
        keyword = "COLOR="
        ikeywd = hdr.find(keyword)
        magics_color = (ikeywd != -1)
        if magics_color:
            col = hdr[ikeywd + len(keyword) : ikeywd + len(keyword) + 4] # substring for r, g, a
            global_rgba = (ord(col[0]), ord(col[1]), ord(col[2]), ord(col[3]))
            if global_rgba not in self.colors:
                self.colors.append(global_rgba)

        # 4 bytes for number of facets
        self.nfacets = struct.unpack("<i", fl.read(4))[0]

        nfacets = 0
        # we dont loop over self.nfacets so we can recover any broken headers showing
        # a wrong number of facets
        while True:
            #50 byte records with normals and vertices per facet
            if not fl.read(12): # override normal
                break

            try:
                r = fl.read(36)
                if (not r):
                    break
                xyz = struct.unpack("<9f", r) # little endian
                lrc = fl.read(2) # padding
                if not lrc:
                    break
                rc = struct.unpack("<h", lrc)
            except struct.error as e:
                print("STLTools, BinaryReadFacets, error:", e)
                print("Read ", nfacets, "triangles; STL header gives: ", self.nfacets, " triangles")
                break

            hascolor = rc[0] & 1
            if hascolor:
                r = rc[0] & 63488 >> 10
                g = rc[0] & 1984 >> 5
                b = rc[0] & 62 >> 1
                if (r, g, b) not in self.colors:
                    self.colors.append((r, g, b))

            tn = TriangleNormal(xyz[0], xyz[1], xyz[2], xyz[3], xyz[4], xyz[5], xyz[6], xyz[7], xyz[8])
            if tn == None:
                self.ndegenerate = self.ndegenerate + 1

            pushcolor = True
            if self.filtercolors:
                pushcolor = (magics_color and not hascolor and global_rgba in self.filtercolors) or (hascolor and (r, g, b) in self.filtercolors)

            pushangle = True
            if self.filterangle:
                pushangle = tn[2] >= self.filterangle[0] and tn[2] < self.filterangle[1]

            if fs and pushcolor and pushangle:
                fs.PushTriangle(xyz[0], xyz[1], xyz[2], xyz[3], xyz[4], xyz[5], xyz[6], xyz[7], xyz[8])

            if pushcolor:
                self.mr.PushTriangle(xyz[0], xyz[1], xyz[2], xyz[3], xyz[4], xyz[5], xyz[6], xyz[7], xyz[8])
                nfacets += 1

        if not self.filtercolors and (self.nfacets != nfacets):
            print("Warning: Number of facets according to header: %d, number of facets read: %d" % (self.nfacets, nfacets))
        if self.filtercolors:
            print("Total number of facets: %d, number of facets read: %d" % (self.nfacets, nfacets))
        self.nfacets = nfacets


    def AsciiReadFacets(self, fl, fs = None):
        lines = fl.readlines()
        xyz = []
        for l in lines:
            tpl = self.ReadVertex(l)
            if tpl:
                xyz.append(tpl[0])
                xyz.append(tpl[1])
                xyz.append(tpl[2])

            if len(xyz) == 9:
                if not TriangleNormal(xyz[0], xyz[1], xyz[2], xyz[3], xyz[4], xyz[5], xyz[6], xyz[7], xyz[8]):
                    self.ndegenerate += 1
                if (fs):
                    fs.PushTriangle(xyz[0], xyz[1], xyz[2], xyz[3], xyz[4], xyz[5], xyz[6], xyz[7], xyz[8])

                self.nfacets += 1
                self.mr.PushTriangle(xyz[0], xyz[1], xyz[2], xyz[3], xyz[4], xyz[5], xyz[6], xyz[7], xyz[8])
                xyz = []

    def ReadFacets(self, fl, fs = None):
        if self.IsAscii(fl):
            self.AsciiReadFacets(fl, fs)
        else:
            self.BinaryReadFacets(fl, fs)



class writerbase:
    def __init__(self, workplane):
        self.workplane = workplane

    def ApplyWorkplane(self, p):
        pn = []
        for i in range(4):
            pn.append(self.workplane[i][0] * p[0] + self.workplane[i][1] * p[1] + self.workplane[i][2] * p[2] + self.workplane[i][3])
        if pn[-1] != 1.0:
            return (pn[0] / pn[-1], pn[1] / pn[-1], pn[2] / pn[-1])
        return (pn[0], pn[1], pn[2])



###########################################################################
class writer(writerbase):
    def __init__(self, fn, write_ascii = False):
        writerbase.__init__(self, None)
        self.fn = fn
        self.ascii = write_ascii
        self.scale = 1.0

    def write(self, fc):
        if self.ascii:
            self.fl = open(self.fn, "w")
        else:
            self.fl = open(self.fn, "wb")

        nfacets = 0
        for t in range(fc.nfacets):
            x0, y0, z0, x1, y1, z1, x2, y2, z2 = fc.GetFacet(t)
            if (TriangleNormal(x0, y0, z0, x1, y1, z1, x2, y2, z2) != None):
                nfacets += 1

        self.WriteHeader(self.fl, nfacets)
        for t in range(fc.nfacets):
            x0, y0, z0, x1, y1, z1, x2, y2, z2 = fc.GetFacet(t)
            self.WriteFacet(x0, y0, z0, x1, y1, z1, x2, y2, z2)

        self.WriteFooter(self.fl)
        self.fl.flush()
        self.fl.close()

    def WriteHeader(self, fl, nfacets):
        if self.ascii:
            fl.write("solid\n")
        else:
            str = b"Stereolithography                                                               "
            assert(len(str) == 80)
            fl.write(str)
            fl.write(struct.pack("<i", nfacets))
            
    def WriteFacet(self, x0, y0, z0, x1, y1, z1, x2, y2, z2, skip_degenerated = True):
        if self.scale != 1.0:
            x0 *= self.scale
            y0 *= self.scale
            z0 *= self.scale
            x1 *= self.scale
            y1 *= self.scale
            z1 *= self.scale
            x2 *= self.scale
            y2 *= self.scale
            z2 *= self.scale
        if self.workplane:
            x0, y0, z0 = self.ApplyWorkplane((x0, y0, z0))
            x1, y1, z1 = self.ApplyWorkplane((x1, y1, z1))
            x2, y2, z2 = self.ApplyWorkplane((x2, y2, z2))
        # calculate facet normal
        n = TriangleNormal(x0, y0, z0, x1, y1, z1, x2, y2, z2)
        if n == None:
            if skip_degenerated: return
            n = (0.0, 0.0, 0.0)
            
        if self.ascii:
            self.fl.write("facet normal %f %f %f\n" % n)            
            self.fl.write("outer loop\n vertex %f %f %f\n vertex %f %f %f\n vertex %f %f %f\nendloop\nendfacet\n" % 
                          (x0, y0, z0, x1, y1, z1, x2, y2, z2))
        else:
            self.fl.write(struct.pack("<12f2c", n[0], n[1], n[2], x0, y0, z0, x1, y1, z1, x2, y2, z2, b" ", b" "))
        
    def WriteFooter(self, fl):
        if self.ascii:
            fl.write("endsolid\n")

    def PushTriangle(self, x0, y0, z0, x1, y1, z1, x2, y2, z2):
        self.WriteFacet(x0, y0, z0, x1, y1, z1, x2, y2, z2)

class MeasureBoundingBox:
    def __init__(self):
        self.xlo = None
        self.xhi = None
        self.ylo = None
        self.yhi = None
        self.zlo = None
        self.zhi = None

    def PushTriangle(self, x0, y0, z0, x1, y1, z1, x2, y2, z2):
        for v in [(x0, y0, z0), (x1, y1, z1), (x2, y2, z2)]:
            if self.xlo is None or v[0] < self.xlo:
                self.xlo = v[0]
            if self.ylo is None or v[1] < self.ylo:
                self.ylo = v[1]
            if self.zlo is None or v[2] < self.zlo:
                self.zlo = v[2]
            if self.xhi is None or v[0] > self.xhi:
                self.xhi = v[0]
            if self.yhi is None or v[1] > self.yhi:
                self.yhi = v[1]
            if self.zhi is None or v[2] > self.zhi:
                self.zhi = v[2]

    def __str__(self):
        return "X[%f,%f], Y[%f,%f], Z[%f,%f]" % (self.xlo, self.xhi, self.ylo, self.yhi, self.zlo, self.zhi)


###########################################################################
class converter(reader, writerbase):
    def __init__(self, fin = None):
        reader.__init__(self, fin)
        writerbase.__init__(self, None)

        # read to find number of facets, but substract degenerated facets
        self.wr = None

    def convert(self, fout, freadfrom = None):
        if self.fn:
            rmod =  self.isascii and "r" or "rb"        
            fl = open(self.fn, rmod)
            if self.isascii:
                self.AsciiReadFacets(fl)
            else:
                self.BinaryReadFacets(fl)
            fl.close()
            
        elif freadfrom:
            if self.isascii:
                self.AsciiReadFacets(freadfrom)
            else:
                self.BinaryReadFacets(freadfrom)
            freadfrom.seek(0) # rewind to start
            
        #self.wr = writer(fout, not self.isascii)
        self.wr = writer(fout)
        #wmod = self.isascii and "wb" or "w"
        wmod = "wb"
        self.fpout = open(fout, wmod)
        self.wr.fl = self.fpout
        self.wr.WriteHeader(self.fpout, self.nfacets - self.ndegenerate)
    
        self.ndegenerate = 0    
        if self.fn:
            rmod =  self.isascii and "r" or "rb"        
            fl = open(self.fn, rmod)
            if self.isascii:
                self.AsciiReadFacets(fl, self)
            else:
                self.BinaryReadFacets(fl, self)
            fl.close()

        elif freadfrom:
            if self.isascii:
                self.AsciiReadFacets(freadfrom, self)
            else:
                self.BinaryReadFacets(freadfrom, self)

        self.wr.WriteFooter(self.fpout)
        self.fpout.close()

    def PushTriangle(self, x0, y0, z0, x1, y1, z1, x2, y2, z2):
        if self.wr != None:
            if self.workplane:
                x0, y0, z0 = self.ApplyWorkplane((x0, y0, z0))
                x1, y1, z1 = self.ApplyWorkplane((x1, y1, z1))
                x2, y2, z2 = self.ApplyWorkplane((x2, y2, z2))
            self.wr.WriteFacet(x0, y0, z0, x1, y1, z1, x2, y2, z2) 



###########################################################################
# use all the options flag.  could have -tk which causes it to import using tk, -in, -out
# design all the settings so it works as pipe, or as files.
# stltools --in=file.stl --out=fil1.stl -b/-a if --out missing then piping
# stltools --tk does the following.
# stltools --in=file.stl --stats prints bounding box etc.
if __name__ == '__main__':
    import sys, os
    useFileDialog = (len(sys.argv) == 1)
    if useFileDialog:
        import tkFileDialog
        fin = tkFileDialog.askopenfilename(
                    defaultextension = '*.stl',
                    filetypes = [('Stereolithography','*.stl'),('all files','*.*')],
                    title = "Open STL")
    else:
        fin = sys.argv[1]
    a = converter(fin)
#    a.workplane = ((1, 0, 0, 50), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
#    a.workplane = ((.707, -.707, 0, 0), (.707, .707, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))

    t = a.isascii and "Save as STL (Binary format)" or "Save as STL (ASCII format)"
    if useFileDialog:
        fout = tkFileDialog.asksaveasfilename(
                    defaultextension = '*.stl',
                    filetypes = [('Stereolithography','*.stl'),('all files','*.*')],
                    title = t)
    else:
        head, tail = os.path.split(sys.argv[1])
        fout = os.path.join(head, "%s%s" % (a.isascii and "bin" or "ascii", tail))

    a.convert(fout)


# solid
# ...

# facet normal 0.00 0.00 1.00
#    outer loop
#      vertex  2.00  2.00  0.00
#      vertex -1.00  1.00  0.00
#      vertex  0.00 -1.00  0.00
#    endloop
#  endfacet
# ...
# endsolid
