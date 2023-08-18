import solara
from pathlib import Path
from typing import Optional, cast
import numpy as np
import dxchange
import tomopy
import os

# import napari

# Fiji executable
Fiij_exe = solara.reactive('/opt/fiji-linux64/Fiji.app/ImageJ-linux64')
Fiji_exe_stack = Fiij_exe.value + ' -macro FolderOpener_virtual.ijm '

h5file = solara.reactive("")
recon_dir = solara.reactive("/home/gianthk/Data/BEATS/IH/scratch/pippo/recon")
cor_dir = solara.reactive("/home/gianthk/Data/BEATS/IH/scratch/pippo/cor")
ncore = solara.reactive(4)
algorithms = ["gridrec", "fbp_cuda"]
algorithm = solara.reactive("gridrec")
# COR_range_min = solara.reactive(1260)
# COR_range_max = solara.reactive(1300)
norm_auto = solara.reactive(True)
COR_range = solara.reactive((1260, 1300)) # COR_range_min.value, COR_range_max.value
COR_slice_ind = solara.reactive(1000) # int(projs.shape[0]/2)
COR_steps = [0.5, 1, 2, 5, 10]
COR_step = solara.reactive(1)
COR_auto = solara.reactive(True)
continuous_update = solara.reactive(True)
COR = solara.reactive(1280)
CORguess = solara.reactive(1280)
COR_algorithms = ["Vo", "TomoPy"]
COR_algorithm = solara.reactive("Vo")
h5dir = "~/Data/" # remove??
projs = np.zeros([0,0,0])
# flats = None
# darks = None
theta = np.zeros(0)
loaded_file = solara.reactive(False)
process_status = solara.reactive(False)
sino_range = solara.reactive((980, 1020))
averaging = solara.reactive("median")
# os.system(Fiji_exe_stack + cor_dir+'{:04.2f}'.format(COR[0])+'.tiff &')

def view_projs_with_napari():
    print("not implemented yet")
    # viewer = napari.view_image(projs)

def view_cor_with_fiji():
    print("not implemented yet")
    os.system(Fiji_exe_stack + cor_dir.value + '/{:04.2f}'.format(COR_range.value[0]) + '.tiff &')

def load_and_normalize(filename):
    global projs
    # global flats
    # global darks
    global theta
    global loaded_file
    process_status.set(True)

    projs, flats, darks, theta = dxchange.read_aps_32id(filename, exchange_rank=0, sino=(sino_range.value[0], sino_range.value[1], 1))
    loaded_file.set(True)

    print("Dataset size: ", projs[:, :, :].shape[:], " - dtype: ", projs.dtype)
    print("Flat fields size: ", flats[:, :, :].shape[:])
    print("Dark fields size: ", darks[:, :, :].shape[:])
    print("Theta array size: ", theta.shape[:])

    if norm_auto.value:
        projs = tomopy.normalize(projs, flats, darks, ncore=ncore.value, averaging=averaging.value)
        print("Sinogram: normalized.")

        projs = tomopy.minus_log(projs, ncore=ncore.value)
        print("Sinogram: - log transformed.")

    if COR_auto.value:
        if COR_algorithm.value == "Vo":
            CORguess.value = tomopy.find_center_vo(projs, ncore=ncore.value)
            print("Automatic detected COR: ", CORguess.value, " - tomopy.find_center_vo")
        elif COR_algorithm.value == "TomoPy":
            CORguess.value = tomopy.find_center(projs, theta, init=projs.shape[2]/2, tol=0.5)
            print("Automatic detected COR: ", CORguess.value, " - tomopy.find_center")

        COR.set(CORguess.value)
        COR_range.set((CORguess.value-20, CORguess.value+20))

    process_status.set(False)

def write_cor():
    process_status.set(True)
    tomopy.write_center(projs,
                        theta,
                        cor_dir.value,
                        [COR_range.value[0], COR_range.value[1], COR_step.value],
                        ind=int(COR_slice_ind.value-sino_range.value[0])
                        )
    print("Reconstructed slice with COR range: ", ([COR_range.value[0], COR_range.value[1], COR_step.value]))
    process_status.set(False)

@solara.component
def DispH5FILE():
    # solara.Markdown("## Dataset information")
    # solara.Markdown(f"**File name**: {h5file.value}")
    return solara.Markdown(f'''
            ## Dataset information
            * File name: <mark>`{h5file.value}`</mark>
            * Proj size: {projs[:, :, :].shape[:]}
            * Sinogram range: `{sino_range.value}`
            * Recon dir: <mark>`{recon_dir.value}`</mark>
            * COR dir: <mark>`{cor_dir.value}`</mark>
            ''')
    # solara.Markdown(f"* Sinogram range: `{sino_range.value}`")
    # solara.Markdown(f"* Recon dir: {recon_dir.value}")
    # solara.Markdown(f"COR dir: {cor_dir.value}")

@solara.component
def CORdisplay():
    with solara.Card("", style={"max-width": "800px"}, margin=0, classes=["my-2"]):
        with solara.Row(gap="10px", justify="space-around"):
            solara.InputFloat("COR guess", value=CORguess, continuous_update=False)
            # solara.InputText("COR", value=COR, continuous_update=continuous_update.value)
            SetCOR()

@solara.component
def CORinspect():

    # COR_range_min, set_COR_range_min = solara.use_state(COR_range.value[0])  # local state
    # solara.Markdown(f"### COR inspection")

    # with solara.Row(gap="20px", justify="space-around"):
    with solara.Column(): # style={"width": "450px"}
        with solara.Row():
            # solara.InputInt("Min", value=COR_range_min, continuous_update=False, on_value=set_COR_range_min)
            solara.Markdown(f"Min: {COR_range.value[0]}")
            solara.SliderRangeInt("COR range", value=COR_range, step=5, min=0, max=projs.shape[2], thumb_label="always")
            solara.Markdown(f"Max: {COR_range.value[1]}")
        # solara.Markdown(f"COR range: {COR_range.value}")
        with solara.Row():
            solara.SliderInt("COR slice", value=COR_slice_ind, step=5, min=sino_range.value[0], max=sino_range.value[1], thumb_label="always")
            solara.SliderValue("COR step", value=COR_step, values=COR_steps)

@solara.component
def SetCOR():
    solara.InputFloat("Your COR choice", value=COR, continuous_update=True)

@solara.component
def CORwrite():
    solara.Button(label="Write images with COR range", icon_name="mdi-play", on_click=lambda: write_cor())
    solara.ProgressLinear(process_status.value)
    solara.Button(label="inspect COR range images", icon_name="mdi-eye", on_click=lambda: view_cor_with_fiji())

@solara.component
def NapariViewer():
    with solara.Card("Napari viewer", style={"max-width": "500px"}, margin=0, classes=["my-2"]):
        with solara.Row(gap="10px", justify="space-around"):
            solara.Button(label="Sinogram", icon_name="mdi-eye", on_click=lambda: view_projs_with_napari(), text=True, outlined=True) # , attributes={"href": github_url, "target": "_blank"}
            solara.Button(label="Reconstruction", icon_name="mdi-eye", on_click=lambda: view_recon_with_napari(), text=True, outlined=True) # , attributes={"href": github_url, "target": "_blank"}

@solara.component
def FijiViewer():
    with solara.Card("Fiji viewer", style={"max-width": "500px"}, margin=0, classes=["my-2"]):
        with solara.Row(gap="10px", justify="space-around"):
            solara.Button(label="COR range", icon_name="mdi-eye", on_click=lambda: view_cor_with_fiji(), text=True, outlined=True) # , attributes={"href": github_url, "target": "_blank"}
            solara.Button(label="Reconstruction", icon_name="mdi-eye", on_click=lambda: view_recon_with_fiji(), text=True, outlined=True) # , attributes={"href": github_url, "target": "_blank"}

@solara.component
def FileSelect():
    with solara.Card("Select HDF5 dataset file", margin=0, classes=["my-2"], style={"max-height": "400px"}): # style={"max-width": "800px"},
        global h5file
        global h5dir

        # h5file, set_file = solara.use_state_or_update(cast(Optional[Path], None))
        # h5file, set_file = solara.use_state(cast(Optional[Path], None))
        h5dir, set_directory = solara.use_state(Path(h5dir).expanduser())

        solara.FileBrowser(can_select=False, directory=h5dir, on_directory_change=set_directory, on_file_open=h5file.set)

@solara.component
def FileLoad():
    with solara.Card("", margin=0, classes=["my-2"]): # style={"max-width": "800px"},
        global h5file

        with solara.Column():
            solara.SliderRangeInt("Sinogram range", value=sino_range, min=0, max=2160, thumb_label="always")
            with solara.Row(): # gap="10px", justify="space-around"
                # with solara.Column():
                solara.Button(label="Load data", icon_name="mdi-cloud-download", on_click=lambda: load_and_normalize(h5file.value), style={"height": "40px", "width": "400px"})
                solara.Switch(label="Normalize", value=norm_auto, style={"height": "20px"})
                solara.Switch(label="Guess Center Of Rotation", value=COR_auto, style={"height": "20px"})

            solara.ProgressLinear(process_status.value)

@solara.component
def DatasetInfo():
    global h5file
    global projs
    global loaded_file

    # if loaded_file.value:
    with solara.VBox():
        solara.Markdown("### Dataset information")
        solara.Info(f"File name: {h5file.value}", dense=True)
        solara.Info(f"Proj size: {projs[:, :, :].shape[:]}", dense=True)

@solara.component
def Recon():
    with solara.Card("CT reconstruction", style={"max-width": "800px"}, margin=0, classes=["my-2"]):
        with solara.Column():
            solara.Select("Algorithm", value=algorithm, values=algorithms)
            solara.Button(label="Reconstruct", icon_name="mdi-car-turbocharger", on_click=lambda: load_and_normalize(h5file))
            solara.Button(label="Inspect", icon_name="mdi-eye", on_click=lambda: load_and_normalize(h5file))
            solara.Button(label="Write to disk", icon_name="mdi-content-save-all-outline", on_click=lambda: load_and_normalize(h5file))

@solara.component
def Settings():
    with solara.Card("Default settings", style={"max-width": "500px"}, margin=0, classes=["my-2"]):
        solara.InputInt("Number of cores", value=ncore, continuous_update=False)
        solara.Select("Algorithm", value=algorithm, values=algorithms)
        solara.InputText("Reconstruction directory", value=recon_dir, continuous_update=False)
        solara.Switch(label="Auto normalize dataset after loading", value=norm_auto, style={"height": "20px"})
        solara.Switch(label="Attempt auto COR once dataset is loaded", value=COR_auto, style={"height": "40px"})
        solara.Select("Automatic COR algorithm", value=COR_algorithm, values=COR_algorithms)
        solara.InputText("COR directory", value=cor_dir, continuous_update=False)
        solara.InputText("FIJI launcher", value=Fiij_exe, continuous_update=False)
        solara.InputText("Sinogram averaging:", value=averaging, continuous_update=False)

@solara.component
def Page():
    with solara.Sidebar():
        with solara.Card(margin=0, elevation=0):
            DispH5FILE()
            SetCOR()
            NapariViewer()
            FijiViewer()
            # DatasetInfo()
            # solara.Markdown("This is the sidebar at the home page!")

    with solara.Card("Load dataset"):
        solara.Title("Al-Recon. CT reconstruction for dummies")
        # solara.Markdown("This is the home page")
        FileSelect()
        FileLoad()
        DatasetInfo()

@solara.component
def Layout(children):
    return solara.AppLayout(children=children)
