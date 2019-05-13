from distutils.spawn import find_executable
from astropy.time import Time
from astropy import units as uni
from astropy.io import fits
from astropy.wcs import WCS
from astropy import coordinates as coord
from astropy import constants as const
import numpy as np
import glob, os
#import pylab
from DDFacet.Other import MyLogger
log=MyLogger.getLogger("ClassSaveResults")
from DDFacet.ToolsDir.rad2hmsdms import rad2hmsdms
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as pylab
from DDFacet.Other.progressbar import ProgressBar
from pyrap.images import image
from dynspecms_version import version

def GiveMAD(X):
    return np.median(np.abs(X-np.median(X)))

class ClassSaveResults():
    def __init__(self, DynSpecMS):
        self.DynSpecMS=DynSpecMS
        self.DIRNAME="DynSpecs_%s"%self.DynSpecMS.OutName
        
        #image  = self.DynSpecMS.Image
        #self.ImageData=np.squeeze(fits.getdata(image, ext=0))

        self.ImageI=self.DynSpecMS.ImageI
        if self.ImageI and os.path.isfile(self.DynSpecMS.ImageI):
            self.im=self.imI=image(self.DynSpecMS.ImageI)
            self.ImageIData=self.imI.getdata()[0,0]

            
        self.ImageV=self.DynSpecMS.ImageV
        if self.ImageV and os.path.isfile(self.ImageV):
            self.imV=image(self.DynSpecMS.ImageV)
            self.ImageVData=self.imV.getdata()[0,1]
        else:
            self.ImageVData=self.ImageIData.copy()
            self.imV=self.imI
            self.ImageVData=np.random.randn(*self.ImageVData.shape)
            self.ImageV=self.ImageI

        self.CatFlux=np.zeros((self.DynSpecMS.NDir,),dtype=[('Name','S200'),("ra",np.float64),("dec",np.float64),('Type','S200'),("IDFacet",np.int32),
                                                            ("FluxI",np.float32),("FluxV",np.float32),("sigFluxI",np.float32),("sigFluxV",np.float32)])
        self.CatFlux=self.CatFlux.view(np.recarray)
        
        os.system("rm -rf %s"%self.DIRNAME)
        os.system("mkdir -p %s/TARGET"%self.DIRNAME)
        os.system("mkdir -p %s/OFF"%self.DIRNAME)
        #os.system("mkdir -p %s/PNG"%self.DIRNAME)

    def tarDirectory(self):
        print>>log,"Taring the result directory"
        ss="tar -zcvf %s.tgz %s > /dev/null 2>&1"%(self.DIRNAME,self.DIRNAME)
        print>>log,"  ... executing %s"%ss
        os.system(ss)


    def WriteFits(self):
        if self.DynSpecMS.DoJonesCorr_kMS:
            self.CatFlux.IDFacet[:]=self.DynSpecMS.DicoJones_kMS['IDJones'][:]

        for iDir in range(self.DynSpecMS.NDir):
            self.WriteFitsThisDir(iDir)

        self.WriteFitsThisDir(0,Weight=True)

    def SaveCatalog(self):
        FileName = "%s/%s.npy"%(self.DIRNAME,"Catalog")
        print>>log,"Saving flux catalogs in %s"%FileName
        np.save(FileName,self.CatFlux)
        
    def GiveSubDir(self,Type):
        SubDir="OFF"
        if Type!="Off": SubDir="TARGET"
        return SubDir

    def WriteFitsThisDir(self,iDir,Weight=False):
        """ Store the dynamic spectrum in a FITS file
        """
        ra,dec=self.DynSpecMS.PosArray.ra[iDir],self.DynSpecMS.PosArray.dec[iDir]
        
        strRA=rad2hmsdms(ra,Type="ra").replace(" ",":")
        strDEC=rad2hmsdms(dec,Type="dec").replace(" ",":")

        fitsname = "%s/%s/%s_%s_%s.fits"%(self.DIRNAME,self.GiveSubDir(self.DynSpecMS.PosArray.Type[iDir]),self.DynSpecMS.OutName, strRA, strDEC)
        if Weight:
            fitsname = "%s/%s.fits"%(self.DIRNAME,"Weights")
            

        # Create the fits file
        prihdr  = fits.Header() 
        prihdr.set('CTYPE1', 'Time', 'Time')
        prihdr.set('CRPIX1', 1., 'Reference')
        prihdr.set('CRVAL1', 0., 'Time at the reference pixel (sec since OBS-STAR)')
        deltaT = (Time(self.DynSpecMS.times[1]/(24*3600.), format='mjd', scale='utc') - Time(self.DynSpecMS.times[0]/(24*3600.), format='mjd', scale='utc')).sec
        prihdr.set('CDELT1', deltaT, 'Delta time (sec)')
        prihdr.set('CUNIT1', 'Time', 'unit')
        prihdr.set('CTYPE2', 'Frequency', 'Frequency')
        prihdr.set('CRPIX2', 1., 'Reference')
        prihdr.set('CRVAL2', self.DynSpecMS.fMin*1e-6, 'Frequency at the reference pixel (MHz)')
        prihdr.set('CDELT2', self.DynSpecMS.ChanWidth*1e-6, 'Delta freq (MHz)')
        prihdr.set('CUNIT2', 'MHz', 'unit')
        prihdr.set('CTYPE3', 'Stokes parameter', '1=I, 2=Q, 3=U, 4=V')
        prihdr.set('CRPIX3', 1., 'Reference')
        prihdr.set('CRVAL3', 1., 'frequence at the reference pixel')
        prihdr.set('CDELT3', 1., 'Delta stokes')
        prihdr.set('CUNIT3', '', 'unit')
        prihdr.set('DATE-CRE', Time.now().iso.split()[0], 'Date of file generation')
        prihdr.set('OBSID', self.DynSpecMS.OutName, 'LOFAR Observation ID')
        prihdr.set('CHAN-WID', self.DynSpecMS.ChanWidth, 'Frequency channel width')
        prihdr.set('FRQ-MIN', self.DynSpecMS.fMin, 'Minimal frequency')
        prihdr.set('FRQ-MAX', self.DynSpecMS.fMax, 'Maximal frequency')
        prihdr.set('OBS-STAR', self.DynSpecMS.tStart, 'Observation start date')
        prihdr.set('OBS-STOP', self.DynSpecMS.tStop, 'Observation end date')
        prihdr.set('RA_RAD', ra, 'Pixel right ascension')
        prihdr.set('DEC_RAD', dec, 'Pixel declination')
        prihdr.set('NAME', self.DynSpecMS.PosArray.Name[iDir], 'Name of the source in the source list')
        prihdr.set('ORIGIN', 'DynSpecMS '+version(),'Created by')
        
        if Weight:
            Gn = self.DynSpecMS.DicoGrids["GridWeight"][iDir,:, :, :].real # dir, time, freq, pol
        else:
            Gn = self.DynSpecMS.GOut[iDir,:, :, :].real

        hdu = fits.PrimaryHDU(np.rollaxis(Gn, 2), header=prihdr)

        hdu.writeto(fitsname, clobber=True)


    def PlotSpec(self,Prefix=""):
        # Pdf file of target positions
        pdfname = "%s/%s_TARGET%s.pdf"%(self.DIRNAME,self.DynSpecMS.OutName,Prefix)
        print>>log,"Making pdf overview: %s"%pdfname
        pBAR = ProgressBar(Title="Making pages")        
        NPages=self.DynSpecMS.NDirSelected #Selected
        iDone=0
        pBAR.render(0, NPages)
        with PdfPages(pdfname) as pdf:
            for iDir in range(self.DynSpecMS.NDir):
                self.fig = pylab.figure(1, figsize=(15, 15))
                if self.DynSpecMS.PosArray.Type[iDir]=="Off": continue
                self.PlotSpecSingleDir(iDir)
                pdf.savefig(bbox_inches='tight')
                pylab.close()
                iDone+=1
                pBAR.render(iDone, NPages)

        # Pdf file of off positions
        NPages=self.DynSpecMS.NDir-self.DynSpecMS.NDirSelected #Off pix
        if NPages==0: return
        pdfname = "%s/%s_OFF%s.pdf"%(self.DIRNAME,self.DynSpecMS.OutName,Prefix)
        print>>log,"Making pdf overview: %s"%pdfname
        pBAR = ProgressBar(Title="Making pages")
        pBAR.render(0, NPages)
        iDone=0
        with PdfPages(pdfname) as pdf:
            for iDir in range(self.DynSpecMS.NDir):
                self.fig = pylab.figure(1, figsize=(15, 15))
                if self.DynSpecMS.PosArray.Type[iDir]!="Off": continue
                self.PlotSpecSingleDir(iDir)
                pdf.savefig(bbox_inches='tight')
                pylab.close()
                iDone+=1
                pBAR.render(iDone, NPages)

        # # Pdf smoothed of target positions
        # pdfname = "%s/%s_TARGET_Smoothed%s.pdf"%(self.DIRNAME,self.DynSpecMS.OutName,Prefix)
        # print>>log,"Making pdf overview: %s"%pdfname
        # pBAR = ProgressBar(Title="Making pages")        
        # NPages=self.DynSpecMS.NDirSelected #Selected
        # iDone=0
        # pBAR.render(0, NPages)
        # with PdfPages(pdfname) as pdf:
        #     for iDir in range(self.DynSpecMS.NDir):
        #         self.fig = pylab.figure(1, figsize=(15, 15))
        #         if self.DynSpecMS.PosArray.Type[iDir]=="Off": continue
        #         self.PlotSpecSingleDir(iDir)
        #         pdf.savefig(bbox_inches='tight')
        #         pylab.close()
        #         iDone+=1
        #         pBAR.render(iDone, NPages)

                
    def PlotSpecSingleDir(self, iDir=0, BoxArcSec=300.):
        label = ["I", "Q", "U", "V"]

        pylab.clf()
        if find_executable("latex") is not None:
            pylab.rc('text', usetex=True)
        font = {'family':'serif', 'serif': ['Times']}
        pylab.rc('font', **font)
        

        # Figure properties
        bigfont   = 8
        smallfont = 6
        ra, dec = np.degrees(self.DynSpecMS.PosArray.ra[iDir]), np.degrees(self.DynSpecMS.PosArray.dec[iDir])
        strRA  = rad2hmsdms(self.DynSpecMS.PosArray.ra[iDir], Type="ra").replace(" ", ":")
        strDEC = rad2hmsdms(self.DynSpecMS.PosArray.dec[iDir], Type="dec").replace(" ", ":")
        #freqs = self.DynSpecMS.FreqsAll.ravel() * 1.e-6 # in MHz
        t0 = Time(self.DynSpecMS.times[0]/(24*3600.), format='mjd', scale='utc')
        t1 = Time(self.DynSpecMS.times[-1]/(24*3600.), format='mjd', scale='utc')
        times = np.linspace(0, (t1-t0).sec/60., num=self.DynSpecMS.GOut[0, :, :, 0].shape[1], endpoint=True)
        freqs = np.linspace(self.DynSpecMS.fMin,self.DynSpecMS.fMax,num=self.DynSpecMS.GOut[0, :, :, 0].shape[0], endpoint=True)*1e-6
        image  = self.DynSpecMS.ImageI

        if (image is None) | (not os.path.isfile(image)):
            # Just plot a series of dynamic spectra
            for ipol in range(4):
                # Gn = self.DynSpecMS.GOut[iDir,:, :, ipol].T.real
                # sig = np.median(np.abs(Gn))
                # mean = np.median(Gn)
                # pylab.subplot(2, 2, ipol+1)
                # pylab.imshow(Gn, interpolation="nearest", aspect="auto", vmin=mean-3*sig, vmax=mean+10*sig)
                # pylab.title(label[ipol])
                # pylab.colorbar()
                # pylab.ylabel("Time bin")
                # pylab.xlabel("Freq bin")
                Gn = self.DynSpecMS.GOut[iDir,:, :, ipol].real
                AG=np.abs(Gn)
                sig  = GiveMAD(Gn)
                mean = np.median(Gn)
                ax1 = pylab.subplot(2, 2, ipol+1)
                spec = pylab.pcolormesh(times, freqs, Gn, cmap='bone_r', vmin=mean-3*sig, vmax=mean+10*sig, rasterized=True)
                ax1.axis('tight')
                cbar = pylab.colorbar()
                cbar.ax.tick_params(labelsize=6)
                pylab.text(times[-1]-0.1*(times[-1]-times[0]), freqs[-1]-0.1*(freqs[-1]-freqs[0]), label[ipol], horizontalalignment='center', verticalalignment='center', fontsize=bigfont)
                if ipol==2 or ipol==3:
                    pylab.xlabel("Time (min since %s)"%(t0.iso), fontsize=bigfont)
                pylab.ylabel("Frequency (MHz)", fontsize=bigfont)
                pylab.setp(ax1.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
                pylab.setp(ax1.get_yticklabels(), rotation='horizontal', fontsize=smallfont)
        else:
            # Plot the survey image and the dynamic spectra series
            # ---- Dynamic spectra I  ----
            axspec = pylab.subplot2grid((5, 2), (2, 0), colspan=2)
            Gn   = self.DynSpecMS.GOut[iDir,:, :, 0].real
            #sig  = np.std(np.abs(Gn))
            AG=np.abs(Gn)
            sig  = GiveMAD(Gn)
            mean = np.median(Gn)
            #spec = pylab.pcolormesh(times, freqs, Gn, cmap='bone_r', vmin=mean-3*sig, vmax=mean+10*sig, rasterized=True)
            spec = pylab.imshow(Gn, interpolation="nearest", cmap='bone_r', vmin=mean-3*sig, vmax=mean+10*sig, extent=(times[0],times[-1],self.DynSpecMS.fMin*1.e-6,self.DynSpecMS.fMax*1.e-6),rasterized=True) 
            axspec.axis('tight')
            cbar = pylab.colorbar(fraction=0.046, pad=0.01)
            cbar.ax.tick_params(labelsize=smallfont)
            cbar.set_label(r'Flux density (Jy)', fontsize=8, horizontalalignment='center') 
            pylab.text(times[-1]-0.02*(times[-1]-times[0]), freqs[-1]-0.1*(freqs[-1]-freqs[0]), 'I', horizontalalignment='center', verticalalignment='center', fontsize=bigfont+2)
            pylab.text(times[0]+0.02*(times[-1]-times[0]), freqs[0]+0.1*(freqs[-1]-freqs[0]), r"$\sigma =$ %.3f Jy"%sig, horizontalalignment='left', verticalalignment='center', fontsize=bigfont+2)
            pylab.xlabel("Time (min since %s)"%(t0.iso), fontsize=bigfont)
            pylab.ylabel("Frequency (MHz)", fontsize=bigfont)
            pylab.setp(axspec.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
            pylab.setp(axspec.get_yticklabels(), rotation='horizontal', fontsize=smallfont)
            # ---- Dynamic spectra L  ----
            axspec = pylab.subplot2grid((5, 2), (3, 0), colspan=2)
            Gn   = np.sqrt(self.DynSpecMS.GOut[iDir,:, :, 1].real**2. + self.DynSpecMS.GOut[iDir,:, :, 2].real**2.)
            AG=np.abs(Gn)
            sig  = GiveMAD(Gn)

            mean = np.median(Gn) 
            #spec = pylab.pcolormesh(times, freqs, Gn, cmap='bone_r', vmin=0, vmax=mean+10*sig, rasterized=True)
            spec = pylab.imshow(Gn, interpolation="nearest", cmap='bone_r', vmin=mean-3*sig, vmax=mean+10*sig, extent=(times[0],times[-1],self.DynSpecMS.fMin*1.e-6,self.DynSpecMS.fMax*1.e-6), rasterized=True) 
            axspec.axis('tight')
            cbar = pylab.colorbar(fraction=0.046, pad=0.01)
            cbar.ax.tick_params(labelsize=smallfont)
            cbar.set_label(r'Flux density (Jy)', fontsize=8, horizontalalignment='center') 
            pylab.text(times[-1]-0.02*(times[-1]-times[0]), freqs[-1]-0.1*(freqs[-1]-freqs[0]), 'L', horizontalalignment='center', verticalalignment='center', fontsize=bigfont+2)
            pylab.text(times[0]+0.02*(times[-1]-times[0]), freqs[0]+0.1*(freqs[-1]-freqs[0]), r"$\sigma =$ %.3f Jy"%sig, horizontalalignment='left', verticalalignment='center', fontsize=bigfont+2)
            pylab.xlabel("Time (min since %s)"%(t0.iso), fontsize=bigfont)
            pylab.ylabel("Frequency (MHz)", fontsize=bigfont)
            pylab.setp(axspec.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
            pylab.setp(axspec.get_yticklabels(), rotation='horizontal', fontsize=smallfont)
            # ---- Dynamic spectra V  ----
            axspec = pylab.subplot2grid((5, 2), (4, 0), colspan=2)
            Gn   = self.DynSpecMS.GOut[iDir,:, :, 3].real
            AG=np.abs(Gn)
            sig  = GiveMAD(Gn)

            mean = np.median(Gn) 
            #spec = pylab.pcolormesh(times, freqs, Gn, cmap='bone_r', vmin=mean-3*sig, vmax=mean+10*sig, rasterized=True)
            spec = pylab.imshow(Gn, interpolation="nearest", cmap='bone_r', vmin=mean-5*sig, vmax=mean+5*sig, extent=(times[0],times[-1],self.DynSpecMS.fMin*1.e-6,self.DynSpecMS.fMax*1.e-6), rasterized=True) 
            axspec.axis('tight')
            cbar = pylab.colorbar(fraction=0.046, pad=0.01)
            cbar.ax.tick_params(labelsize=smallfont)
            cbar.set_label(r'Flux density (Jy)', fontsize=8, horizontalalignment='center') 
            pylab.text(times[-1]-0.02*(times[-1]-times[0]), freqs[-1]-0.1*(freqs[-1]-freqs[0]), 'V', horizontalalignment='center', verticalalignment='center', fontsize=bigfont+2)
            pylab.text(times[0]+0.02*(times[-1]-times[0]), freqs[0]+0.1*(freqs[-1]-freqs[0]), r"$\sigma =$ %.3f Jy"%sig, horizontalalignment='left', verticalalignment='center', fontsize=bigfont+2)
            pylab.xlabel("Time (min since %s)"%(t0.iso), fontsize=bigfont)
            pylab.ylabel("Frequency (MHz)", fontsize=bigfont)
            pylab.setp(axspec.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
            pylab.setp(axspec.get_yticklabels(), rotation='horizontal', fontsize=smallfont)

            # ---- Plot mean vs time  ----
            # ax2 = pylab.subplot2grid((5, 2), (0, 1))
            # Gn_i = self.DynSpecMS.GOut[iDir,:, :, 0].real
            # meantime = np.mean(Gn_i, axis=0)
            # stdtime  = np.std(Gn_i, axis=0)
            # ax2.fill_between(times, meantime-stdtime, meantime+stdtime, facecolor='#B6CAC8', edgecolor='none', zorder=-10)
            # pylab.plot(times, meantime, color='black')
            # pylab.axhline(y=0, color='black', linestyle=':')
            # pylab.xlabel("Time (min since %s)"%(t0.iso), fontsize=bigfont)
            # pylab.ylabel("Mean (Stokes I)", fontsize=bigfont)
            # pylab.setp(ax2.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
            # pylab.setp(ax2.get_yticklabels(), rotation='horizontal', fontsize=smallfont)
            # ymin, vv = np.percentile((meantime-stdtime).ravel(), [5, 95])
            # vv, ymax = np.percentile((meantime+stdtime).ravel(), [5, 95])
            # ax2.set_ylim([ymin, ymax])
            # ax2.set_xlim([times[0], times[-1]])

            # ---- Plot mean vs frequency  ----
            # ax3 = pylab.subplot2grid((5, 2), (1, 1))
            # meanfreq = np.mean(Gn_i, axis=1)
            # stdfreq = np.std(Gn_i, axis=1)
            # ax3.fill_between(freqs.ravel(), meanfreq-stdfreq, meanfreq+stdfreq, facecolor='#B6CAC8', edgecolor='none', zorder=-10)
            # ax3.plot(freqs.ravel(), meanfreq, color='black')
            # ax3.axhline(y=0, color='black', linestyle=':')
            # pylab.xlabel("Frequency (MHz)", fontsize=bigfont)
            # pylab.ylabel("Mean (Stokes I)", fontsize=bigfont)
            # pylab.setp(ax3.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
            # pylab.setp(ax3.get_yticklabels(), rotation='horizontal', fontsize=smallfont)
            # ymin, vv = np.percentile((meanfreq-stdfreq).ravel(), [5, 95])
            # vv, ymax = np.percentile((meanfreq+stdfreq).ravel(), [5, 95])
            # ax3.set_ylim([ymin,ymax])
            # ax3.set_xlim([freqs.ravel()[0], freqs.ravel()[-1]])

            # ---- Image ----
            npix = 1000
            header = fits.getheader(image)
            data   = self.ImageIData # A VERIFIER
            f,p,_,_=self.im.toworld([0,0,0,0])
            _,_,xc,yc=self.im.topixel([f,p,self.DynSpecMS.PosArray.dec[iDir], self.DynSpecMS.PosArray.ra[iDir]])
            yc,xc=int(xc),int(yc)

            wcs    = WCS(header).celestial
            CDEL   = wcs.wcs.cdelt
            pos_ra_pix, pos_dec_pix = wcs.wcs_world2pix(np.degrees(self.DynSpecMS.PosArray.ra[iDir]), np.degrees(self.DynSpecMS.PosArray.dec[iDir]), 1)
            #cenpixra, cenpixdec = wcs.wcs_world2pix(np.degrees(self.DynSpecMS.PosArray.ra[iDir]), np.degrees(self.DynSpecMS.PosArray.dec[iDir]), 1)
            #print("central pixels {}, {}".format(cenpixx, cenpixy))
            #print>>log, "central pixels {}, {}".format(cenpixx, cenpixy)
            nn=self.ImageIData.shape[-1]

            box=int(abs((BoxArcSec/3600.)/wcs.wcs.cdelt[0]))
            def giveBounded(x):
                x=np.max([0,x])
                return np.min([x,nn-1])

            x0=giveBounded(xc-box)
            x1=giveBounded(xc+box)
            y0=giveBounded(yc-box)
            y1=giveBounded(yc+box)
            
            DataBoxed=self.ImageIData[y0:y1,x0:x1]
            FluxI=self.ImageIData[yc,xc]
            sigFluxI=GiveMAD(DataBoxed)

            newra_cen, newdec_cen = wcs.wcs_pix2world( (x1+x0)/2., (y1+y0)/2., 1)
            wcs.wcs.crpix  = [ DataBoxed.shape[1]/2., DataBoxed.shape[0]/2. ] # update the WCS object
            wcs.wcs.crval = [ newra_cen, newdec_cen ]
            #stop
            if DataBoxed.size>box:
                std=GiveMAD(DataBoxed)
                vMin, vMax    = (-5.*std, 30*std)
                ax1 = pylab.subplot2grid((5, 2), (0, 0), rowspan=2, projection=wcs)
                im = pylab.imshow(DataBoxed, interpolation="nearest", cmap='bone_r', aspect="auto", vmin=vMin, vmax=vMax, origin='lower', rasterized=True)
                #pylab.text((ra_crop[1]-ra_crop[0])/16, (dec_crop[1]-dec_crop[0])/16, r"$\sigma =$ %.3f mJy"%rms, horizontalalignment='left', verticalalignment='center', fontsize=bigfont+2)
                cbar = pylab.colorbar()#(fraction=0.046*2., pad=0.01*4.)
                
                ax1.set_xlabel(r'RA (J2000)')
                raax = ax1.coords[0]
                raax.set_major_formatter('hh:mm:ss')
                raax.set_ticklabel(size=smallfont)
                ax1.set_ylabel(r'Dec (J2000)')
                decax = ax1.coords[1]
                decax.set_major_formatter('dd:mm:ss')
                decax.set_ticklabel(size=smallfont)
                ax1.autoscale(False)
                # newcenpixra, newcenpixdec = wcs.wcs_world2pix(np.degrees(self.DynSpecMS.PosArray.ra[iDir]), np.degrees(self.DynSpecMS.PosArray.dec[iDir]), 1)
                # pylab.plot(newcenpixra, newcenpixdec, 'o', markerfacecolor='none', markeredgecolor='red', markersize=bigfont) # plot a circle at the target
                cbar.set_label(r'Flux density (mJy)', fontsize=bigfont, horizontalalignment='center')
                cbar.ax.tick_params(labelsize=smallfont)
                pylab.setp(ax1.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
                pylab.setp(ax1.get_yticklabels(), rotation='horizontal', fontsize=smallfont)
                
                ra_cen, dec_cen = wcs.wcs_world2pix(np.degrees(self.DynSpecMS.PosArray.ra[iDir]), np.degrees(self.DynSpecMS.PosArray.dec[iDir]), 1)
                #pylab.plot(ra_cen, dec_cen, 'o', markerfacecolor='none', markeredgecolor='red', markersize=bigfont) # plot a circle at the target
                #pylab.plot(newra_cen, newdec_cen, 'o', markerfacecolor='none', markeredgecolor='red', markersize=bigfont) # plot a circle at the target
                pylab.plot(DataBoxed.shape[1]/2., DataBoxed.shape[0]/2., 'o', markerfacecolor='none', markeredgecolor='red', markersize=bigfont) # plot a circle at the target
                
                pylab.text(DataBoxed.shape[0]*0.9, DataBoxed.shape[1]*0.9, 'I', horizontalalignment='center', verticalalignment='center', fontsize=bigfont+2)        


            # ---- Image V ----
            ## -- CHANGE TO IMAGE STOKES V -- ##
            headerv = fits.getheader(self.ImageV) # TO BE MODIFIED
            datav   = self.ImageVData[:, :] # TO BE MODIFIED
            f,p,_,_=self.imV.toworld([0,0,0,0]) # self.im TO BE MODIFIED
            _,_,xc,yc=self.imV.topixel([f,p,self.DynSpecMS.PosArray.dec[iDir], self.DynSpecMS.PosArray.ra[iDir]])
            yc,xc=int(xc),int(yc)
            wcs    = WCS(headerv).celestial
            CDEL   = wcs.wcs.cdelt
            pos_ra_pix, pos_dec_pix = wcs.wcs_world2pix(np.degrees(self.DynSpecMS.PosArray.ra[iDir]), np.degrees(self.DynSpecMS.PosArray.dec[iDir]), 1)
            nn=self.ImageVData.shape[-1]
            #boxv = int(box / np.abs(wcs.wcs.cdelt[0]) * np.abs(CDEL[0]))
            boxv=int(abs((BoxArcSec/3600.)/wcs.wcs.cdelt[0]))
            def giveBounded(x):
                x=np.max([0,x])
                return np.min([x,nn-1])
            x0=giveBounded(xc-boxv)
            x1=giveBounded(xc+boxv)
            y0=giveBounded(yc-boxv)
            y1=giveBounded(yc+boxv)
            DataBoxed=datav[y0:y1,x0:x1]

            FluxV=datav[yc,xc]
            sigFluxV=GiveMAD(DataBoxed)
            self.CatFlux.FluxV[iDir]=FluxV
            self.CatFlux.FluxI[iDir]=FluxI
            self.CatFlux.sigFluxV[iDir]=sigFluxV
            self.CatFlux.sigFluxI[iDir]=sigFluxI
            self.CatFlux.Name[iDir]=self.DynSpecMS.PosArray.Name[iDir]
            self.CatFlux.Type[iDir]=self.DynSpecMS.PosArray.Type[iDir]
            self.CatFlux.ra[iDir]=self.DynSpecMS.PosArray.ra[iDir]
            self.CatFlux.dec[iDir]=self.DynSpecMS.PosArray.dec[iDir]
            
            newra_cen, newdec_cen = wcs.wcs_pix2world( (x1+x0)/2., (y1+y0)/2., 1)
            wcs.wcs.crpix  = [ DataBoxed.shape[1]/2., DataBoxed.shape[0]/2. ] # update the WCS object
            wcs.wcs.crval = [ newra_cen, newdec_cen ]
            if DataBoxed.size>box:
                std=GiveMAD(DataBoxed)
                vMin, vMax    = (-5.*std, 30*std)
                ax1 = pylab.subplot2grid((5, 2), (0, 1), rowspan=2, projection=wcs)
                im = pylab.imshow(DataBoxed, interpolation="nearest", cmap='bone_r', aspect="auto", vmin=vMin, vmax=vMax, origin='lower', rasterized=True)
                cbar = pylab.colorbar()
                ax1.set_xlabel(r'RA (J2000)')
                raax = ax1.coords[0]
                raax.set_major_formatter('hh:mm:ss')
                raax.set_ticklabel(size=smallfont)
                ax1.set_ylabel(r'Dec (J2000)')
                decax = ax1.coords[1]
                decax.set_major_formatter('dd:mm:ss')
                decax.set_ticklabel(size=smallfont)
                ax1.autoscale(False)
                cbar.set_label(r'Flux density (mJy)', fontsize=bigfont, horizontalalignment='center')
                cbar.ax.tick_params(labelsize=smallfont)
                pylab.setp(ax1.get_xticklabels(), rotation='horizontal', fontsize=smallfont)
                pylab.setp(ax1.get_yticklabels(), rotation='horizontal', fontsize=smallfont)
                ra_cen, dec_cen = wcs.wcs_world2pix(np.degrees(self.DynSpecMS.PosArray.ra[iDir]), np.degrees(self.DynSpecMS.PosArray.dec[iDir]), 1)
                pylab.plot(DataBoxed.shape[1]/2., DataBoxed.shape[0]/2., 'o', markerfacecolor='none', markeredgecolor='red', markersize=bigfont) # plot a circle at the target
                pylab.text(DataBoxed.shape[0]*0.9, DataBoxed.shape[1]*0.9, 'V', horizontalalignment='center', verticalalignment='center', fontsize=bigfont+2) 


        #pylab.subplots_adjust(wspace=0.15, hspace=0.30)
        pylab.figtext(x=0.5, y=0.92, s="Name: %s, Type: %s, RA: %s, Dec: %s"%(self.DynSpecMS.PosArray.Name[iDir].replace('_', ' '), self.DynSpecMS.PosArray.Type[iDir].replace('_', ' '), strRA, strDEC), fontsize=bigfont+2, horizontalalignment='center', verticalalignment='bottom')
        #pylab.suptitle("Name: %s, Type: %s, RA: %s, Dec: %s"%(self.DynSpecMS.PosArray.Name[iDir], self.DynSpecMS.PosArray.Type[iDir], self.DynSpecMS.PosArray.ra[iDir], self.DynSpecMS.PosArray.dec[iDir]))



