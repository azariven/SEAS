"""

This is a submodule for the data loader to load cross sections
Should not be called by user


need to add grid interpretation.





"""
import os
import sys
import h5py
import numpy as np
import miepython as mp
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d, RegularGridInterpolator

DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(DIR, '../..'))

import SEAS_Main.Physics.astrophysics as calc
import SEAS_Utils.System_Utils.optimization as opt
from SEAS_Main.Simulation.cloud import Simple_Gray_Cloud_Simulator

VERBOSE = False

def main_molecule_selector(molecule, 
                           preference_order=["Exomol","HITRAN_Lines","HITRAN_Xsec","NIST"],
                           auxillary=True):
    """
    Due to our data coming from multiple sources, we need a way to automatically   
    select which molecule gets used in the simulation.
    
    not used at the moment
    """

    for preference in preference_order:
        
        if preference == "Exomol":
            pass
        elif preference == "HITRAN_Lines":
            pass
        elif preference == "HITRAN_Xsec":
            pass
        elif preference == "NIST":
            pass

#Xsec_Loader




class Cross_Section_Loader():
    """
    Absorption Cross Section Loader.
    
    is there a way to get rid of needing in have user_input
    loaded in "load_HITRAN"? it's already loaded with __init__
    """

    def __init__(self, user_input,reuse=True,memory=False,pre_def_nu=False):
        
        self.user_input = user_input
        self.reuse = reuse
        self.memory = memory
        self.pre_def_nu = pre_def_nu
        
        
        self.normalized_pressure        = user_input["Prototype"]["Normalized_Pressure"]
        self.normalized_temperature     = user_input["Prototype"]["Normalized_Temperature"]
        
        # old database, supported during the transition, will be renamed to HDF5_DB_old once fixed
        # new database, will be used in the future, but name will be changed to HDF5_DB
        # a txt file should exist in the database folder explaining the construct of the database
        # including wavenumber span, molecule resolution, etc.
        
        # This should be a parameter in the user_input
        self.DB_DIR = user_input["Data_IO"]["File_Path"]["DB_DIR"]
                    
            
        if "New" in self.DB_DIR:
            wn_bin = [[400.,2000.,0.4],[2000.,10000.,2],[10000.,30000.,5]]
            self.db_nu = np.concatenate([np.arange(x[0],x[1],x[2]) for x in wn_bin])
    
        else: # For backward compatibility
            with h5py.File("%s/%s.hdf5"%(self.DB_DIR,"nu"), "r") as dnu:
                self.db_nu = np.array(dnu["results"])        

        if pre_def_nu:
            self.nu = user_input["Xsec"]["nu"]
        else:
            self.nu = self.db_nu
            
        self.xsec = {}
        
        
        # for interpolating the cross section
        # self.x = self.user_input["Xsec"]["Molecule"]["T_Grid"]
        # self.X = self.normalized_temperature 
        

    @opt.timeit
    def load_CIA(self, molecule="H2-H2", savepath=None, savename=None):

        if molecule != "H2-H2":
            print("CIA other than H2-H2 is not implemented")
            sys.exit()

        """
        if cache != None:
            self.xsec[molecule] = cache
        """
    
        hash = self.user_input["Data_IO"]["Hash"]
        savepath = savepath or "../../SEAS_Input/Cross_Section/Generated/%s"%hash
        savename = savename or "%s_cia_%s.npy"%(molecule,hash)
        filepath = os.path.join(savepath,savename)
        
        if self.reuse and os.path.isfile(filepath):
            
            nu, normalized_cia_profile = np.load(filepath,allow_pickle=True) 
            #self.nu doesn't need to be loaded again
            if VERBOSE:
                print("%s CIA Cross Section Loaded"%molecule)

        else:
            HITRAN_CIA = self.user_input["Xsec"]["CIA"]["Source"]
            
            H2_CIA = os.path.join(HITRAN_CIA,"H2-H2_2011.cia")
            temperature = []
            with open(H2_CIA) as f:
                data = f.read().split("\n")
                if data[-1] == "":
                    data = data[:-1]
                        
                data_point = int(data[0][40:47].strip()) # identify how many datapoint exist for this molecule
                data_grid = np.reshape(np.array(data),(-1,data_point+1)) # reshape the data by temperature blocks
                cia_grid = np.zeros((len(data_grid),data_point))
                
                for i,info in enumerate(data_grid):
                    temperature.append(int(float(info[0][47:54].strip()))) # extract temperature from first line
                    n,x = np.array([x.split() for x in info[1:]],dtype="float").T # process data from the remain line in the block
                    cia_grid[i] = np.array(x,dtype="float")
                
            self.user_input["Xsec"]["CIA"]["T_Grid"] = temperature
    
            normalized_cia_profile = self.grid_interpolate(cia_grid,n,select="cia")

            if not os.path.isdir(savepath):
                os.makedirs(savepath)   
            np.save(filepath, [self.nu, normalized_cia_profile]) # no need to save self.nu,?
            if VERBOSE:
                print("%s CIA Cross Section Saved"%molecule)
        
        return normalized_cia_profile
    
    @opt.timeit     
    def load_HITRAN(self, molecule, savepath=None, savename=None):
        """
        Loading molecule cross section from database or precalculated
        interpolate cross section along pressure temperature profile
        # This step can be optimized for retrieval by only loading it once if TP profile doesn't change
        """
        
    
        hash = self.user_input["Data_IO"]["Hash"]
        savepath = savepath or "../../SEAS_Input/Cross_Section/Generated/%s"%hash
        savename = savename or "%s_%s.npy"%(molecule,hash)
        filepath = os.path.join(savepath,savename)
        
        
        if self.reuse and os.path.isfile(filepath):
            self.nu,xsec = np.load(filepath,allow_pickle=True) #self.nu doesn't need to be loaded again
            print("%s Cross Section Profile Loaded from file"%molecule)
            return xsec,xsec
            
        else:
            if molecule in ["O","H"]:
                grid_xsec, profile_xsec = self.load_empty()
                return grid_xsec, profile_xsec
            
            else: # need to change this in the future when not loading from HITRAN sources
                print(molecule)
                grid_xsec, profile_xsec = self.load_HITRAN_single(molecule)
                return grid_xsec, profile_xsec
                

                
            
            
            # not dealing with saving xsec for now
            """
            if not os.path.isdir(savepath):
                os.makedirs(savepath)   
            np.save(filepath, [self.nu,self.xsec[molecule]]) # no need to save self.nu,?
            if VERBOSE:
                print("%s Cross Section Saved"%molecule)
            """
    @opt.timeit   
    def load_empty(self):
        
        T_Grid = np.concatenate([np.arange(100,300,50),
                                 np.arange(300,1000,100),
                                 np.arange(1000,3200,200)
                                 ])
    
        P_Grid = 10.**np.arange(-10,3)
        
        NP = np.array(self.user_input["Prototype"]["Normalized_Pressure"])/101300
        NT = np.array(self.user_input["Prototype"]["Normalized_Temperature"])
        
        
        # findind the boundary based on initial temperature pressure guess
        # this can be problematic for retrieval when temperature goes beyond bound. 
        # need a way to append to xsec grid in memory or ... simply be less restricting with bounds?
        Tmin, Tmax, Pmin, Pmax = np.min(NT),np.max(NT),np.min(NP),np.max(NP)
        
        # might want to change the index to reflect actual temperature range
        # since finer grids will make range smaller as well
        TL = np.argmin(T_Grid < Tmin) - 1
        TR = np.argmax(T_Grid > Tmax) + 1
        PL = np.argmin(P_Grid < Pmin) - 1
        PR = np.argmax(P_Grid > Pmax) + 1
        
        T_Grid = T_Grid[TL:TR]  # need to handle index error here
        P_Grid = P_Grid[PL:PR][::-1] # the old grid read high pressure first
        
        self.user_input["Xsec"]["Molecule"]["T_Grid"] = T_Grid
        self.user_input["Xsec"]["Molecule"]["P_Grid"] = P_Grid
        
        grid = np.zeros((len(P_Grid),len(T_Grid),len(self.nu)))
        
        wave = len(self.nu)
        layer = len(self.normalized_pressure)
        xsec = np.zeros((layer,wave))
        
        return grid, xsec
   
    @opt.timeit
    def load_HITRAN_single(self,molecule):
        """
        Loading molecular cross section for given pressure and temperature
        Will have to be optimized when doing tp profile retrieval.
        This will work when only retrieving on mixing ratio.
        Don't even need to interpolate if matched temperature and pressure
        will see how long the interpolation takes, then judge.
        """
        
        
        
        if "New" in self.DB_DIR:
            
            if self.memory and self.user_input["Xsec"]["Loaded"] == True:
                print("interpolating grid from memeory")
                xsec = self.user_input["Xsec"]["Grid"][molecule]
                
                # need to check if new xsec exceed bound of previous TP grid in the future
                #self.user_input["Xsec"]["Molecule"]["T_Grid"] = T_Grid
                #self.user_input["Xsec"]["Molecule"]["P_Grid"] = P_Grid
                
            
            else:
                print("interpolating grid from file")
                # replace this with dynamic grid detector
                T_Grid = np.concatenate([np.arange(100,300,50),
                                 np.arange(300,1000,100),
                                 np.arange(1000,3200,200)
                                 ])
    
                P_Grid = 10.**np.arange(-10,3)
                
                NP = np.array(self.user_input["Prototype"]["Normalized_Pressure"])/101300
                NT = np.array(self.user_input["Prototype"]["Normalized_Temperature"])
                
                
                # findind the boundary based on initial temperature pressure guess
                # this can be problematic for retrieval when temperature goes beyond bound. 
                # need a way to append to xsec grid in memory or ... simply be less restricting with bounds?
                Tmin, Tmax, Pmin, Pmax = np.min(NT),np.max(NT),np.min(NP),np.max(NP)
                
                # might want to change the index to reflect actual temperature range
                # since finer grids will make range smaller as well
                TL = np.argmin(T_Grid < Tmin) - 1
                TR = np.argmax(T_Grid > Tmax) + 1
                PL = np.argmin(P_Grid < Pmin) - 1
                PR = np.argmax(P_Grid > Pmax) + 1
                
                T_Grid = T_Grid[TL:TR]  # need to handle index error here
                P_Grid = P_Grid[PL:PR][::-1] # the old grid read high pressure first
                
                self.user_input["Xsec"]["Molecule"]["T_Grid"] = T_Grid
                self.user_input["Xsec"]["Molecule"]["P_Grid"] = P_Grid
                
                
                xsec = np.zeros((len(P_Grid),len(T_Grid),len(self.nu)))
                for i,P in enumerate(P_Grid):
                    for j,T in enumerate(T_Grid):
                        filename = os.path.join(self.DB_DIR,molecule,"%s_T%s_P%s.hdf5"%(molecule,T,int(np.log10(P))))
                     
                        with h5py.File(filename, "r") as f:
                            if self.pre_def_nu:
                                xsec[i][j] = np.interp(self.nu,self.db_nu,np.array(f["xsec"]))
                            else:
                                xsec[i][j] = np.array(f["xsec"])
                            
            return xsec, self.grid_interpolate(xsec)

        else:
            
            if self.memory and self.user_input["Xsec"]["Loaded"] == True:
                xsec = user_input["Xsec"]["Grid"][molecule]
                return xsec, self.grid_interpolate(xsec)
            
            else:
                with h5py.File("%s/%s.hdf5"%(self.DB_DIR,molecule), "r") as xsec:
                    return np.array(xsec["results"]), self.grid_interpolate(np.array(xsec["results"])) # 24, 9, 12000 grid             
                
              
            
            
    def load_HITRAN_raw_grid(self,molecule):
        
        with h5py.File("%s/%s.hdf5"%(self.DB_DIR,molecule), "r") as xsec:
            return np.array(xsec["results"]) # 24, 9, 12000 grid 
        
    def load_Exomol(self, molecule):
        
        self.xsec = ["Exomol_%s not implemented"%molecule]
            
    def load_NIST(self, molecule):
        
        x1,y1 = load_NIST_spectra(bio_molecule,["wn","T"],True)
        
        Pref = 10000.
        Tref = 300.        
        nref = Pref/(BoltK*Tref)
        lref = 0.05        

        y1 = np.array(y1)+(1-(np.mean(y1)+np.median(y1))/2)
        y1new = []
        for i in y1:
            if i > 1:
                y1new.append(1)
            else:
                y1new.append(i)
        y1 = y1new     
        
        # interpolation
        yinterp = np.interp(self.nu,x1,y1)
        xsec = -np.log(yinterp)/(nref*lref)*10000  # multiply by a factor of 10000 due to unit conversion
    
        
        
        return xsec 

    def load_PNNL(self, molecule):
        
        datapath = "../../SEAS_Input/Cross_Section/HITRAN_Xsec/isoprene/C5-H8_298.1K-760.0K_600.0-6500.0_0.11_N2_505_43.xsc"
        
        file = open(datapath,"r").read().split("\n")
        
        header = file[0]
        headerinfo = header.split()
        
        numin   = headerinfo[1]
        numax   = headerinfo[2]
        npts    = headerinfo[3]
        T       = headerinfo[4]
        P       = headerinfo[5]
        maxres  = headerinfo[6]
        molecule= headerinfo[7]
        broaden = headerinfo[8]
        note    = headerinfo[9]
        max = maxres[:-5]
        res = maxres[-5:]
        
        
        ylist = np.array(np.concatenate([i.split() for i in file[1:]]),dtype=float)
        xlist = np.linspace(float(numin),float(numax),len(ylist))
        yinterp = np.interp(self.nu,xlist,ylist)
        
        layer = len(self.normalized_pressure)
        profile_xsec = np.tile(yinterp,layer).reshape(layer,-1)   
        
        return profile_xsec
        
    @opt.timeit
    def grid_interpolate(self,xsec_grid,nu=None,select="molecule"):
        """
        Hypothesis:
            Would interpolating from a smaller xsec_grid be beneficial for the speed?
            we only need to load in a grid that is slightly larger than the TP profile, not the whole database.
        """
        
        wave = len(self.nu)
        layer = len(self.normalized_pressure)
        normalized_xsec = np.zeros((layer,wave))
        
        if select == "molecule":
            
            
            T_Grid = np.array(self.user_input["Xsec"]["Molecule"]["T_Grid"],dtype=float)
            P_Grid = np.array(self.user_input["Xsec"]["Molecule"]["P_Grid"],dtype=float)
            
            # creating the 2D interpolation function
            # the [::-1] is because it needs to be strictly ascending
            f = RegularGridInterpolator((np.log10(P_Grid[::-1]),T_Grid, self.nu),xsec_grid[::-1])
        
            if "New" in self.DB_DIR: # new database is using bar for pressure unit instead of Pa
                normalized_pressure = np.array(self.normalized_pressure)/101300.
            else:
                normalized_pressure = self.normalized_pressure
            
            for i,(P_E,T_E) in enumerate(zip(np.log10(normalized_pressure),self.normalized_temperature)):
                normalized_xsec[i] = f(np.array([np.ones(wave)*P_E, np.ones(wave)*T_E, self.nu]).T)
            
            # need to check if interpolated molecule xsec is within range
                    
                    
        elif select == "cia":
            T_Grid = np.array(self.user_input["Xsec"]["CIA"]["T_Grid"],dtype=float)
            f = RegularGridInterpolator((T_Grid, nu), xsec_grid,
                                        bounds_error=False,fill_value=0)
 
            for i, T_E in enumerate(self.normalized_temperature):
                normalized_xsec[i] = f(np.array([np.ones(wave)*T_E, self.nu]).T)
        
        return normalized_xsec

    def load_rayleigh_scattering(self,molecules):
        """
        currently not caring about biosignature molecule rayleigh?
        """
        
        Rayleigh_array = {}
        for molecule in molecules:
            Rayleigh_array[molecule] = calc.calc_rayleigh(molecule, self.nu)
        print("Rayleigh Scatter Loaded")
        return Rayleigh_array
    
    @opt.timeit
    def load_gray_cloud(self):

        normalized_cloud_xsec = []
        cloud_deck          = float(self.user_input["Xsec"]["Cloud"]["Deck"])
        cloud_opacity       = float(self.user_input["Xsec"]["Cloud"]["Opacity"])
        normalized_pressure = np.array(self.user_input["Prototype"]["Normalized_Pressure"],dtype=float)
        
        #c = Simple_Gray_Cloud_Simulator(cloud_deck,cloud_opacity)
        
        for i,P in enumerate(normalized_pressure):
            if P < cloud_deck:
                normalized_cloud_xsec.append(np.zeros(len(self.nu)))
            else:
                normalized_cloud_xsec.append(np.ones(len(self.nu))*cloud_opacity)
        print("Gray Cloud Loaded")
        return normalized_cloud_xsec   
    @opt.timeit
    def load_mie_cloud(self):
        
        normalized_cloud_xsec = []
        normalized_pressure = np.array(self.user_input["Prototype"]["Normalized_Pressure"],dtype=float)
        
        # will update this to np version once testing is done
        cloud_sigma = self.calculate_mie_cloud()
        for i,P in enumerate(normalized_pressure):
            normalized_cloud_xsec.append(cloud_sigma)
        print("Mie Cloud Loaded")
        
        return normalized_cloud_xsec   

    def calculate_mie_cloud(self):
        """
        need to add cache to this instead of generating everytime
        """
        
        Source = self.user_input["Xsec"]["Cloud"]["Source"]
        
        lam, n, k = np.genfromtxt("../../SEAS_Input/Refractive_Index/%s"%Source).T
        
        # The miepython module takes the imaginary as negative
        m = n - 1j*k
        
        mean_radius = float(self.user_input["Xsec"]["Cloud"]["Mean_Radius"])
        std         = float(self.user_input["Xsec"]["Cloud"]["Standard_Deviation"])
        sample      = int(self.user_input["Xsec"]["Cloud"]["Sample_Size"])
        
        # draws 10 sample. Not much difference between 10 and 100. 
        # if use 100, may want to output result to avoid duplicated calculations
        radii = np.random.normal(mean_radius,std,sample)
        
        extinct_xsec = np.zeros((len(radii),len(lam)))
        for i,radius in enumerate(radii):
            x = 2*np.pi*radius/lam
            qext, qsca, qback, g = mp.mie(m,x)
            extinct_xsec[i] = qext*np.pi*(radius/1e4)**2 # 1e4 is because um -> cm so that unit is 1/cm^2    
        
        # calculate the cross section given the data
        cloud_sigma = np.mean(np.array(extinct_xsec),axis=0)
        # Return the cross section interpolated to self.nu
        # This only works in linear?
        
        # this is dizzy, are you sure it is not reversed?
        return np.interp(10000./self.nu, lam, cloud_sigma)

    # 24, 9, 12000
    






