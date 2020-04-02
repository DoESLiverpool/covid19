import sys
sys.path.append("../Prusa_stacks")
from STLTools import reader, writer
import math

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
            if min(zvals) >= zmin and max(zvals) <= zmax:
                filtered.append(t)
        return filtered

    def filterIfInZRange(self, vmove, zrange, mode = "all", copy = False):
        zmin, zmax = zrange
        x, y, z = vmove
        for i, t in enumerate(self.triangles):
            p0 = list(t)[0:3]
            p1 = list(t)[3:6]
            p2 = list(t)[6:9]
            if mode == "all":
                if p0[2] >= zmin and p0[2] <= zmax and p1[2] >= zmin and p1[2] <= zmax and p2[2] >= zmin and p2[2] <= zmax:
                    p0 = [p0[k] + vmove[k] for k in range(3)]
                    p1 = [p1[k] + vmove[k] for k in range(3)]
                    p2 = [p2[k] + vmove[k] for k in range(3)]
            else:

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

    def addTriangles(self, trx):
        self.triangles.extend(trx)
        self.nfacets += len(trx)

class SupportPin:
    def __init__(self, height, origin, rad):
        sides = 6
        self.nfacets = 0
        self.facets = []
        for i in range(sides):
            x0 = origin[0] + rad * math.sin(2 * math.pi * i/sides) 
            y0 = origin[1] + rad * math.cos(2 * math.pi * i/sides)
            if i < sides: 
                x1 = origin[0] + rad * math.sin(2 * math.pi * (i + 1)/sides) 
                y1 = origin[1] + rad * math.cos(2 * math.pi * (i + 1)/sides) 
            else:
                x1 = origin[0] + rad * math.sin(0) 
                y1 = origin[1] + rad * math.cos(0)
            z0 = origin[2]
            z1 = origin[2] + height
            self.facets.append((x0, y0, z0, x1, y1, z0, x1, y1, z1))
            self.facets.append((x1, y1, z1, x0, y0, z1, x0, y0, z0))
            self.nfacets += 2

    def GetFacet(self, i):
        return self.facets[i]


def closestSupport(pos, p):
    dmin = 1.e100
    for pp in pos:
        d = (pp[0] - p[0]) ** 2 + (pp[1] - p[1]) ** 2
        if d < dmin:
            dmin = d
    return math.sqrt(dmin)



if __name__ == "__main__":
    supportDistance = 6 # supports not closer than this


    r = reader()

    f = open("Visor_frame_EUROPE_80mm_4hole_v1.stl", "rb")
    triangles = Triangles()
    r.BinaryReadFacets(f, triangles)
    triangles.nfacets = r.nfacets

    # add supports
    top = triangles.filterByZ(5, 5)
    top.insert(0, (78.9229, -35.0638, 5, 76.3902, -37.0232, 5, 78.8745, -38.0634, 5))
    top.insert(0, (-78.9229, -35.0638, 5, -76.3902, -37.0232, 5, -78.8745, -38.0634, 5))
    top.insert(0, (38.2391, 25.7711, 5, 41.3158, 29.2973, 5, 38.3621, 29.7728, 5))
    top.insert(0, (-38.2391, 25.7711, 5, -41.3158, 29.2973, 5, -38.3621, 29.7728, 5))
    supportPositions = []
    for s in top:
        px = (s[0] + s[3] + s[6])/3.0
        py = (s[1] + s[4] + s[7])/3.0
        pz = s[8]
        if closestSupport(supportPositions, (px, py, pz)) >= supportDistance:
            supportpin = SupportPin(0.25, (px, py, pz), 0.25)
            triangles.addTriangles(supportpin.facets)
            supportPositions.append((px, py, pz))


    w = writer("with_support.stl")
    w.write(triangles)

    # the height of one headband: 5
    height = 5
    # the support in between
    support = 0.25

    # number of additional head bands
    nadd = 16

    # copy headband nadd times
    for c in range(nadd-1):
        triangles.filterIfInZRange((0, 0, (c+1) * (height + support)), (0, height + support), "all", True)
    triangles.filterIfInZRange((0, 0, nadd * (height + support)), (0, height), "all", True)

    w = writer("verkstan_%d.stl" % (nadd))
    w.write(triangles)
