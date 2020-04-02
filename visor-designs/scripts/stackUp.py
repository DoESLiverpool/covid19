from STLTools import reader, writer

class Triangles:
    def __init__(self):
        self.triangles = []

    def PushTriangle(self, x0, y0, z0, x1, y1, z1, x2, y2, z2):
        self.triangles.append((x0, y0, z0, x1, y1, z1, x2, y2, z2))

    def GetFacet(self, i):
        return self.triangles[i]

    def filterByZ(self, zmin, zmax):
        filtered = []
        for t in self.triangles:
            zvals = (t[2], t[5], t[8])
            if min(zvals) >= zmin and max(zvals) < zmax:
                filtered.append(t)
        return filtered

    def filterIfInZRange(self, vmove, zrange, copy = False):
        zmin, zmax = zrange
        x, y, z = vmove
        for i, t in enumerate(self.triangles):
            p0 = list(t)[0:3]
            p1 = list(t)[3:6]
            p2 = list(t)[6:9]
            if p0[2] >= zmin and p0[2] <= zmax:
                p0 = [p0[k] + vmove[k] for k in range(3)]
            if p1[2] >= zmin and p1[2] < zmax:
                p1 = [p1[k] + vmove[k] for k in range(3)]
            if p2[2] >= zmin and p2[2] < zmax:
                p2 = [p2[k] + vmove[k] for k in range(3)]
            tmove = (p0[0], p0[1], p0[2], p1[0], p1[1], p1[2], p2[0], p2[1], p2[2])  
            if tmove != t:
                if not copy:
                    self.triangles[i] = tmove
                else:
                    self.triangles.append(tmove)
                    self.nfacets += 1

 
if __name__ == "__main__":
    r = reader()

    f = open("covid19_headband_quadro_rc31.stl", "rb")
    triangles = Triangles()
    r.BinaryReadFacets(f, triangles)
    triangles.nfacets = r.nfacets

    # the height of one headband: 20.00
    height = 20
    # the support in between
    support = 0.25

    # number of additional head bands
    nadd = 3

    # move top headband up
    triangles.filterIfInZRange((0, 0, nadd * (height + support)), (60.75, 80.8))

    # copy headband below top nadd times
    for c in range(nadd):
        triangles.filterIfInZRange((0, 0, (c+1) * (height + support)), (40.5, 60.51), True)

    w = writer("covid19_headband_quadro_rc31_stack_%d.stl" % (4 + nadd))
    w.write(triangles)
