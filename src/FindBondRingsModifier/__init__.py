#### Find Bond Rings ####
# Tries to find rings of specified sizes in the bond topology.

from ovito.data import *
from ovito.pipeline import ModifierInterface
from traits.api import *
from ovito.traits import OvitoObjectTrait
import networkx as nx
import numpy as np
from ovito.vis import SurfaceMeshVis
import math

class FindBondRingsModifier(ModifierInterface):

    max_ring_size = Range(3, 20, label="Search for ring sizes up to")
    min_ring_size = Range(3, 20, label="Do not show rings smaller than")

    create_mesh = Bool(True, label="Create color mesh")
    mesh_vis = OvitoObjectTrait(SurfaceMeshVis)

    def modify(self, data: DataCollection, frame: int, **kwargs):
        
        Rings = {}
        SortedRings = {}

        if self.min_ring_size > self.max_ring_size:
            raise RuntimeError(f"Parameter [Search for ring sizes up to] cannot be smaller than [Do not show rings smaller than.]")

        if not data.particles.bonds:
            raise RuntimeError("No bonds present in dataset. Please generate or import bond topology.")
        
        if data.particles.bonds.count == 0:
            return

        for i in range(self.min_ring_size , self.max_ring_size+1):
            data.particles_.bonds_.create_property(f"N{i} Ring", data = np.zeros(data.particles.bonds.count))
            data.particles_.create_property(f"N{i} Ring", data = np.zeros(data.particles.count))
            SortedRings[i] = []
            Rings[i] = []
            
        topo = data.particles.bonds.topology
        G = nx.Graph()
        G.add_edges_from(topo)       
        
        bonds_enum = BondsEnumerator(data.particles.bonds)
        
        for i in range(data.particles.count):
            yield i/data.particles.count
            # list of nodes connected to particle/node i with specified depth_limit
            # T is depth first search tree
            if len([bond_index for bond_index in bonds_enum.bonds_of_particle(i)]) == 0:
                continue
            T = nx.dfs_tree(G, source=i, depth_limit=math.ceil(self.max_ring_size/2))

            # Find simple cycles in directed search tree (connections between particle i and max. its Nth next neighbors, where N = ceil(max_ring_size/2))
            result = nx.simple_cycles( nx.subgraph(G, T.nodes).to_directed(True))
        
            for r in result:
                r_len = len(r)
                #only consider results with specified member count
                if r_len <= self.max_ring_size and r_len >= self.min_ring_size:
                    if sorted(r) not in SortedRings[r_len]:
                        l = Rings[r_len]
                        l.append(r)
                        Rings[r_len] = l
                        m = SortedRings[r_len]
                        m.append(sorted(r))
                        SortedRings[r_len] = m
                    for u in range(r_len):
                        edge = (r[u-1], r[u]) 
                        data.particles_[f"N{r_len} Ring_"][r[u-1]] = 1 
                        #print(edge)
                        k = np.nonzero(np.logical_and(topo[:,0] == edge[0], topo[:,1] == edge[1]))[0]
                        j = np.nonzero(np.logical_and(topo[:,1] == edge[0], topo[:,0] == edge[1]))[0]
                        bond_index = k if k.size > 0 else j
                        data.particles_.bonds_[f"N{r_len} Ring_"][bond_index] = 1

        yield "Creating Data Tables"

        for i in range(self.min_ring_size, self.max_ring_size+1):
            nRing_count = len(Rings[i])
            print(f"Number of {i}-membered Rings: {nRing_count} ")
            
            if nRing_count  == 0:
                continue
            data.attributes[f"N{i}-Ring count"] = nRing_count
            table = data.tables.create(identifier=f'n{i}rings-table', title=f'N{i}-Rings', plot_mode=DataTable.PlotMode.NoPlot)
            table.x = table.create_property('Ring members', data=Rings[i])
            table.y = table.create_property('Ring Size', data=[len(x) for x in table.x])
   
        #Histogram showing ring statistics
        table = data.tables.create(identifier='histogram', plot_mode=DataTable.PlotMode.Histogram, title='Ring Statistics')
        table.x = table.create_property('Ring Size', data=np.arange(self.min_ring_size, self.max_ring_size+1))  
        table.y = table.create_property('Counts', data=[len(Rings[i]) for i in range(self.min_ring_size, self.max_ring_size+1)])

        yield "Creating Color Mesh"

        if self.create_mesh == True:
            mesh = data.surfaces.create(identifier='ring_mesh', title='Rings color mesh', domain=data.cell)
            mesh.create_vertices(np.array(data.particles.positions))
            triangle_list = []
            face_property = []
            for i in range(self.min_ring_size, self.max_ring_size+1):
                nRing_count = len(Rings[i])
                if nRing_count  == 0:
                    continue
                for ring in Rings[i]:     
                    for j in range(0,len(ring)-2):
                        vertices_of_face =  [ring[0], ring[1+j], ring[2+j]]
                        triangle_list.append(vertices_of_face)              
                        face_property.append(i) 
            mesh.create_faces(np.reshape(triangle_list, (-1, 3)))
            mesh.faces_.create_property("Ring Size", data = face_property)
            mesh.connect_opposite_halfedges()
            mesh.vis = self.mesh_vis

        print(f"---------------------------------------------")
        print(f"Number of bonds: {data.particles.bonds.count}")
        print(f"Number of particles: {data.particles.count}")
        
        
        