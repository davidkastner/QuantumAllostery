"""Process the raw TeraChem output for future analysis."""

import os
import re
import io
import sys
import glob
import time
import shutil
import pandas as pd
import numpy as np
from itertools import combinations
from collections import OrderedDict
from typing import List, Tuple
from biopandas.pdb import PandasPdb
from Bio.PDB import PDBParser, Vector
import qa.reference
from typing import List


def get_pdb() -> str:
    """
    Searches all directories recursively for a PDB file.

    If more than one PDB is found it will use the first one.
    If no PDB file was found, it will prompt the user for a PDB file path.

    Returns
    -------
    pdb_file : str
        The path of a PDB file within the current directory (recursive).

    Notes
    -----
    Currently it uses the name to distinguish single structures,
    ensembles, and trajectories.
    In the future, this function should check the contents to confirm.

    """
    # A list of all PDB's found after recursive search
    pdb_files = sorted(glob.glob("./**/template.pdb", recursive=True))
    for index, pdb in enumerate(pdb_files):
        # Trajectory PDB's should be marked as ensemble or traj
        if "ensemble" in pdb or "traj" in pdb or "top" in pdb:
            continue
        else:
            pdb_file = pdb_files[index]

    # Multiple or no PDB files found scenarios
    if len(pdb_files) == 1:
        print(f"> Using {pdb_file} as the template PDB.")
    elif len(pdb_files) > 1:
        print(f"> More than one PDB file found -> Using {pdb_file}.")
    else:
        pdb_file = input("No PDB files was found. What is the path to your PDB file? ")

    return pdb_file


def get_xyz() -> str:
    """
    Searches all directories for a XYZ file.

    If more than one XYZ is found it will use the first one.
    If no XYZ file was found it will prompt the user for the XYZ file path.

    Returns
    -------
    xyz_name : str
        The path of a XYZ file within the current directory.

    """
    # Search recursively for an xyz file
    xyz_names = glob.glob("./**/*.xyz", recursive=True)

    # Check the results to confirm that there was only one xyz file found
    if len(xyz_names) == 1:
        xyz_name = xyz_names[0]
        print(f"> Found the coordinate file {xyz_name}.")
    elif len(xyz_names) > 1:
        xyz_name = xyz_names[0]
        print(f"> Found more than one XYZ, using {xyz_name}.")
    else:
        xyz_name = input("No XYZ was found. What is the path to your XYZ? ")

    return xyz_name


def get_atom_count() -> int:
    """
    Finds an xyz file and gets the number of atoms.

    Returns
    -------
    atom_count : int
        The number of atoms in the identified xyz file.
    """
    # Find an xyz file
    xyz_name = get_xyz()
    with open(xyz_name, "r") as xyz_file:
        atom_count = int(xyz_file.readline().strip())

    return atom_count


def combine_xyzs() -> None:
    """
    Combine an arbitrary number of xyz files.

    When generating the input for the QM calculations,
    you may have created a directory of single xyz strucutres.
    This script will recombine them back into a single xyz trajectory.

    """
    xyz_files = glob.glob("*.xyz")
    with open("all_coors.xyz", "w") as all_coors:
        for xyz in xyz_files:
            with open(xyz, "r") as current_xyz:
                all_coors.write(current_xyz.read())


def get_protein_sequence(pdb_path) -> List[str]:
    """
    Gets the full amino acid sequence of your protein.

    See Also
    --------
    qa.plot.heatmap()

    """

    # Get the template file and load it as a pandas dataframe
    pdb_df = PandasPdb().read_pdb(pdb_path).df["ATOM"]

    # Filter the dataframe so there is one entry for each residue
    residues_df = pdb_df[["residue_name", "residue_number"]]
    residues_df = residues_df.drop_duplicates(subset=["residue_number"], keep="first")

    # Convert it to a list of amino acids
    residues_df = residues_df["residue_name"]
    residues_list = residues_df.values.tolist()

    return residues_list


def get_charge_file() -> str:
    """
    Searches all directories for a charge xls file.

    If more than one .xls file is found it will use the first one.
    If no .xls file was found it will prompt the user for the .xls file path.
    This is the standard charge output for TeraChem.

    Returns
    -------
    charge_file : str
        The path of a charge .xls file within the current directory.

    Notes
    -----
    Starts in the directory containing all the directories

    """

    # Get the xls from the current directory
    charge_files = sorted(glob.glob("*.xls"))

    # Check the results to confirm that there was only one .xls file found
    if len(charge_files) == 1:
        charge_file = charge_files[0]
        print(f"> Found the charge file {charge_file}.")
    elif len(charge_files) > 1:
        charge_file = charge_files[0]
        print(f"> Found more than one .xls, using {charge_file}.")
    else:
        charge_file = input("> No .xls was found. What is the path to your .xls? ")

    return charge_file

def combine_sp_xyz():
    """
    Combines single point xyz's for all replicates.

    The QM single points each of a geometry file.
    Combines all those xyz files into.
    Preferential to using the other geometry files to insure they are identical.

    Returns
    -------
    replicate_info : List[tuple()]
        List of tuples with replicate number and frame count for the replicates.

    """
    start_time = time.time()  # Used to report the executation speed

    # Get the directories of each replicate
    primary = os.getcwd()
    replicates = sorted(glob.glob("*/"))
    ignore = ["Analyze/", "Analysis/", "coordinates/", "inputfiles/", "opt-wfn/"]

    xyz_count = 0
    replicate_info = []  # Initialize an empty list to store replicate information

    # Get the name of the structure
    geometry_name = os.getcwd().split("/")[-1]
    out_file = f"{geometry_name}_geometry.xyz"

    with open(out_file, "w") as combined_sp:
        for replicate in replicates:
            if replicate in ignore:
                continue
            else:
                print(f"   > Adding replicate {replicate} structures.")
                os.chdir(replicate)
                os.chdir("coordinates")

                structures = sorted(glob.glob("*.xyz"), key=lambda x: int(re.findall(r'\d+', x)[0]))
                frame_count = 0  # Initialize frame count for each replicate
                for index, structure in enumerate(structures):
                    with open(structure, "r") as file:
                        # Write the header from the first file
                        combined_sp.writelines(file.readlines())
                        xyz_count += 1
                        frame_count += 1

                replicate_info.append((int(replicate[:-1]), frame_count))  # Append replicate information

            # Go back and loop through all the other replicates
            os.chdir(primary)

    total_time = round(time.time() - start_time, 3)  # Time to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tOUTPUT: Combined {xyz_count} single point xyz files.
        \tOUTPUT: Output file is {out_file}.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )

    # Return the list of tuples with replicate information
    return replicate_info 



import os
import glob
import time


def combine_restarts(
    atom_count, all_charges: str = "all_charges.xls", all_coors: str = "all_coors.xyz"
) -> None:
    """
    Collects all charges or coordinates into single xls and xyz files.

    This version determines overlaps by parsing the frame numbers in the title lines
    of `coors.xyz` and adjusts the corresponding lines in `charges.xls`.

    Parameters
    ----------
    all_charges : str
        The name of the file containing all charges in xls format.
    all_coors : str
        The name of the file containing the coordinates in xyz format.
    atom_count : int
        The number of atoms in the structure.

    Notes
    -----
    Run from the directory that contains the run fragments.
    """
    start_time = time.time()  # Clock execution speed

    # Locate all directories containing coordinate and charge files
    directories = sorted(glob.glob("./**/scr*", recursive=True))

    if not directories:
        print("No directories found matching the pattern './**/scr*'. Exiting.")
        return

    # Delete existing combined files if they exist
    if os.path.exists(all_charges):
        os.remove(all_charges)
    if os.path.exists(all_coors):
        os.remove(all_coors)

    # Variables to keep track of the last processed frame
    last_frame = 0
    total_frames = 0

    # Process each directory
    for dir_idx, directory in enumerate(directories):
        coors_file_path = os.path.join(directory, "coors.xyz")
        charge_file_path = os.path.join(directory, "charge.xls")

        if not os.path.exists(coors_file_path) or not os.path.exists(charge_file_path):
            print(f"Skipping {directory}: Missing coors.xyz or charge.xls.")
            continue

        # Read coordinate and charge files
        with open(coors_file_path, "r") as coors_file:
            coors_lines = coors_file.readlines()

        with open(charge_file_path, "r") as charge_file:
            charge_lines = charge_file.readlines()

        # Determine the number of atoms per frame
        lines_per_frame = atom_count + 2

        # Extract frame numbers and their indices from the title lines
        frame_numbers = []
        frame_indices = []
        for i in range(1, len(coors_lines), lines_per_frame):
            title_line = coors_lines[i]
            try:
                frame_number = int(title_line.split()[2])  # Extract frame number
                frame_numbers.append(frame_number)
                frame_indices.append(i - 1)  # Index of the atom count line
            except (IndexError, ValueError):
                print(f"Warning: Could not parse frame number from line: {title_line.strip()}")

        # Identify the starting frame of this run and exclude overlaps
        valid_start_idx = 0
        for idx, frame in enumerate(frame_numbers):
            if frame > last_frame:
                valid_start_idx = idx
                break

        # Update the last processed frame
        if frame_numbers:
            last_frame = frame_numbers[-1]

        # Write the valid frames and charges to the combined files
        with open(all_coors, "a") as all_coors_file:
            for idx in range(valid_start_idx, len(frame_numbers)):
                start = frame_indices[idx]
                end = start + lines_per_frame
                all_coors_file.writelines(coors_lines[start:end])

        with open(all_charges, "a") as all_charges_file:
            if dir_idx == 0:
                # Include header line only once
                all_charges_file.write(charge_lines[0])
            all_charges_file.writelines(charge_lines[valid_start_idx + 1 : len(frame_numbers) + 1])

        # Update the total number of frames
        total_frames += len(frame_numbers) - valid_start_idx

        print(
            f"Processed {directory}: Added frames {frame_numbers[valid_start_idx]} "
            f"to {frame_numbers[-1]} ({len(frame_numbers) - valid_start_idx} frames)."
        )

    # Validate the combined files
    combined_frame_count = 0
    with open(all_coors, "r") as coors:
        for line in coors:
            if "frame" in line:
                combined_frame_count += 1

    total_time = round(time.time() - start_time, 3)  # Seconds to run
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: {combined_frame_count} frames and {total_frames} charges combined.
        \tOUTPUT: Generated {all_charges} and {all_coors}.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def combine_replicates(
    all_charges: str = "all_charges.xls", all_coors: str = "all_coors.xyz"
) -> None:
    """
    Collects charges or coordinates into a xls and xyz file across replicates.

    Parameters
    ----------
    all_charges : str
        The name of the file containing all charges in xls format.
    all_coors.xyz : str
        The name of the file containing the coordinates in xyz format.

    Notes
    -----
    Run from the directory that contains the replicates.
    Run combine_restarts first for if each replicated was run across multiple runs.
    Generalized to combine any number of replicates.

    See Also
    --------
    combine_restarts: Combines restarts and should be run first.
    """

    # General variables
    start_time = time.time()  # Used to report the executation speed
    files = [all_charges, all_coors]  # Files to be concatonated
    charge_files: list[str] = []  # List of the charge file locations
    coors_files: list[str] = []  # List of the coors file locations
    root = os.getcwd()
    dirs = sorted(glob.glob(f"{root}/*/"))  # glob to efficiently grab only dirs
    replicates = len(dirs)  # Only used to report to user

    # Loop through all directories containing replicates
    for dir in dirs:
        if os.path.isfile(f"{dir}{files[0]}") and os.path.isfile(f"{dir}{files[1]}"):
            charge_files.append(f"{dir}{files[0]}")
            coors_files.append(f"{dir}{files[1]}")

    new_file_names = [f"raw_{all_charges}", all_coors]
    file_locations = [charge_files, coors_files]
    # Loop over the file names and their locations
    for file_name, file_location in zip(new_file_names, file_locations):
        # Open a new file where we will write the concatonated output
        with open(file_name, "wb") as outfile:
            for loc in file_location:
                with open(loc, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)

    # The combined charge file now has multiple header lines
    first_line = True
    with open(new_file_names[0], "r") as raw_charge_file:
        with open(files[0], "w") as clean_charge_file:
            for line in raw_charge_file:
                # We want the first line to have the header
                if first_line == True:
                    clean_charge_file.write(line)
                    first_line = False
                # After the first, no lines should contain atom names
                else:
                    if "H" in line:
                        continue
                    else:
                        clean_charge_file.write(line)
    # Delete the charge file with the extra headers to keep the dir clean
    os.remove(new_file_names[0])

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Combined {replicates} replicates.
        \tOUTPUT: Generated {files[0]} and {files[1]} in the current directory.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )

# def combine_restarts(
#     atom_count, all_charges: str = "all_charges.xls", all_coors: str = "all_coors.xyz"
# ) -> None:
#     """
#     Collects all charges or coordinates into single xls and xyz files.

#     Likely the first executed function after generating the raw AIMD data.
#     Trajectories were likely generated over multiple runs.
#     This function combines all coordinate and charge data for each run.

#     Parameters
#     ----------
#     all_charges : str
#         The name of the file containing all charges in xls format.
#     all_coors.xyz : str
#         The name of the file containing the coordinates in xyz format.
#     atom_count : int
#         The number of atoms in the structure

#     Notes
#     -----
#     Run from the directory that contains the run fragments.

#     See Also
#     --------
#     combine_replicates: Combines all the combined trajectories of each replicate into one.

#     """

#     start_time = time.time()  # Clock executation speed

#     # Collect all qmscript.out files
#     out_files = glob.glob("./**/qmscript.out", recursive=True)
#     out_files_count = len(out_files)  # Will report this to user
#     # run_info: The MD restart step, the outfile name, and its scr directory
#     run_info: list[list[int, str, str]] = []

#     # Get the first MD step from out_files to identify where each job restarted
#     # Note: Restarting occurs from the last restart point not the last frame
#     for out_file in out_files:
#         out_content = open(out_file, "r").readlines()
#         for line in out_content:
#             if "MD STEP" in line:
#                 # A list of info about each run [start step, file, scr dir]
#                 md_step = int(line.split()[4])
#                 run_info.append([md_step, out_file])
#                 break

#     # Get the src directory locations for the restart attempt to generate paths
#     scrdir = glob.glob("./**/scr*/", recursive=True)
#     scrdir.sort()  # Sort by modification date
#     run_info.sort()  # Sort by MD step
#     for index, step in enumerate(run_info):
#         # Add the name of the scr directory location to the run_info list
#         step.append(scrdir[index])

#     # Delete so we don't append to a previous version when rerunning
#     if os.path.exists(all_charges):
#         os.remove(all_charges)
#     if os.path.exists(all_coors):
#         os.remove(all_coors)

#     # Use the run_info to open the charge and coordinate files
#     first_run = True
#     for index, run in enumerate(run_info):
#         coors_file = open(f"{run[2]}coors.xyz", "r").readlines()
#         charge_file = open(f"{run[2]}charge.xls", "r").readlines()
#         # Create combined charge and coors files
#         all_coors_file = open(all_coors, "a")
#         all_charges_file = open(all_charges, "a")

#         # First run
#         if first_run:
#             coor_run_end = (run_info[index + 1][0] - 1) * (atom_count + 2)
#             all_coors_file.writelines(coors_file[:coor_run_end])
#             # The first charges line is a special header line that we add once
#             # so we don't need to substract one because it cancels with the index offset
#             charge_run_end = run_info[index + 1][0]
#             all_charges_file.writelines(charge_file[:charge_run_end])
#             first_run = False

#         # Last run
#         elif index == len(run_info) - 1:
#             # Go all the way to the end so a frame isn't left off
#             all_coors_file.writelines(coors_file)
#             all_charges_file.writelines(charge_file[1:])

#         # Other run
#         else:
#             # To get the number of frames in run two,
#             # substract the restart number from the frames in run 1
#             coor_run_end = ((run_info[index + 1][0] - 1) - (run[0] - 1)) * (
#                 atom_count + 2
#             )
#             all_coors_file.writelines(coors_file[:coor_run_end])
#             charge_run_end = (run_info[index + 1][0]) - (run[0] - 1)
#             all_charges_file.writelines(charge_file[1:charge_run_end])

#     # Close files
#     all_coors_file.close()
#     all_charges_file.close()

#     # Check the number of frames in the combined xyz trajectory and print for user
#     coors_frame_count = 0
#     with open(all_coors, "r") as coors:
#         for line in coors:
#             if "frame" in line:
#                 coors_frame_count += 1

#     # Check number of charge frames and print for user
#     charge_frame_count = -1
#     with open(all_charges, "r") as charges:
#         for line in charges:
#             charge_frame_count += 1

#     total_time = round(time.time() - start_time, 3)  # Seconds to run
#     print(
#         f"""
#         \t----------------------------ALL RUNS END----------------------------
#         \tRESULT: {coors_frame_count} frames and {charge_frame_count} charges from {out_files_count} runs.
#         \tOUTPUT: Generated {all_charges} and {all_coors}.
#         \tOUTPUT: {os.path.abspath(os.getcwd())}.
#         \tTIME: Total execution time: {total_time} seconds.
#         \t--------------------------------------------------------------------\n
#         """
#     )

def summed_residue_charge(charge_data: pd.DataFrame, template: str):
    """
    Sums the charges for all atoms by residue.

    Reduces inaccuracies introduced by the limitations of Mulliken charges.

    Parameters
    ----------
    charge_data: pd.DataFrame
        A DataFrame containing the charge data.
    template: str
        The name of the template pdb for the protein of interest.

    Returns
    -------
    sum_by_residues: pd.DataFrame
        The charge data averaged by residue and stored as a pd.DataFrame.

    """
    # Extract the "replicate" column and remove it from the charge_data DataFrame
    replicate_column = charge_data['replicate']
    charge_data = charge_data.drop('replicate', axis=1)

    # Get the residue identifiers (e.g., 1Ala) for each atom
    residues_indentifier = get_residue_identifiers(template)

    # Assign the residue identifiers as the column names of the charge DataFrame
    charge_data.columns = residues_indentifier
    sum_by_residues = charge_data.groupby(by=charge_data.columns, sort=False, axis=1).sum()

    # Add the "replicate" column back to the sum_by_residues DataFrame
    sum_by_residues['replicate'] = replicate_column

    return sum_by_residues


def get_residue_identifiers(template, by_atom=True) -> List[str]:
    """
    Gets the residue identifiers such as Ala1 or Cys24.

    Returns either the residue identifiers for every atom, if by_atom = True
    or for just the unique amino acids if by_atom = False.

    Parameters
    ----------
    template: str
        The name of the template pdb for the protein of interest.
    by_atom: bool
        A boolean value for whether to return the atom identifiers for all atoms

    Returns
    -------
    residues_indentifier: List(str)
        A list of the residue identifiers

    """
    # Get the residue number identifiers (e.g., 1)
    residue_number = (
        PandasPdb().read_pdb(template).df["ATOM"]["residue_number"].tolist()
    )
    # Get the residue number identifiers (e.g., ALA)
    residue_name = PandasPdb().read_pdb(template).df["ATOM"]["residue_name"].tolist()
    # Combine them together
    residues_indentifier = [
        f"{name}{number}" for number, name in zip(residue_number, residue_name)
    ]

    # Return only unique entries if the user sets by_atom = False
    if not by_atom:
        residues_indentifier = list(OrderedDict.fromkeys(residues_indentifier))

    return residues_indentifier


def xyz2pdb(xyz_list: List[str]) -> None:
    """
    Converts an xyz file into a pdb file.

    Parameters
    ----------
    xyz_list: List(str)
        A list of file names that you would like to convert to PDB's

    Note
    ----
    Make sure to manually check the PDB that is read in.
    Assumes no header lines.
    Assumes that the only TER flag is at the end.

    """
    start_time = time.time()  # Used to report the executation speed

    # Search for the XYZ and PDB files names
    pdb_name = get_pdb()
    pdb_file = open(pdb_name, "r").readlines()
    max_atom = int(pdb_file[len(pdb_file) - 3].split()[1])

    for index, xyz in enumerate(xyz_list):
        new_file = open(f"{index}.pdb", "w")
        xyz_file = open(xyz, "r").readlines()
        atom = -1  # Start at -1 to skip the XYZ header
        line_count = 0
        for line in xyz_file:
            line_count += 1
            if atom > 0:
                atom += 1
                try:
                    x, y, z = line.strip("\n").split()[1:5]  # Coordinates from xyz file
                except:
                    print(f"> Script died at {line_count} -> '{line}'")
                    quit()
                pdb_line = pdb_file[atom - 2]  # PDB is two behind the xyz
                new_file.write(
                    f"{pdb_line[0:30]}{x[0:6]}  {y[0:6]}  {z[0:6]}  {pdb_line[54:80]}"
                )
            else:
                atom += 1
            if atom > max_atom:
                atom = -1
                new_file.write("END\n")

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Converted {len(xyz_list)} to pdbs.
        \tOUTPUT: Generated in the current directory.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def xyz2pdb_traj(xyz_name, pdb_name, pdb_template) -> None:
    """
    Converts an xyz trajectory file into a pdb trajectory file.

    Note
    ----
    Make sure to manually check the PDB that is read in.
    Assumes no header lines.
    Assumes that the only TER flag is at the end.

    """

    start_time = time.time()  # Used to report the executation speed

    # Open files for reading
    xyz_file = open(xyz_name, "r").readlines()
    pdb_file = open(pdb_template, "r").readlines()
    max_atom = int(pdb_file[len(pdb_file) - 3].split()[1])
    new_file = open(pdb_name, "w")

    atom = -1  # Start at -1 to skip the XYZ header
    line_count = 0
    for line in xyz_file:
        line_count += 1
        if atom > 0:
            atom += 1
            try:
                x, y, z = line.strip("\n").split()[1:5]  # Coordinates from xyz file
            except:
                print(f"> Script died at {line_count} -> '{line}'")
                quit()
            pdb_line = pdb_file[atom - 2]  # PDB is two behind the xyz
            new_file.write(
                f"{pdb_line[0:30]}{x[0:6]}  {y[0:6]}  {z[0:6]}  {pdb_line[54:80]}"
            )
        else:
            atom += 1
        if atom > max_atom:
            atom = -1
            new_file.write("END\n")

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Converted {xyz_name} to {pdb_name}.
        \tOUTPUT: Generated {pdb_name} in the current directory.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def xyz2pdb_ensemble() -> None:
    """
    Converts an xyz trajectory file into a pdb ensemble.

    Note
    ----
    Assumes that the only TER flag is at the end.
    """

    # Search for the XYZ and PDB files names
    start_time = time.time()  # Used to report the executation speed
    pdb_name = get_pdb()
    xyz_name = get_xyz()
    # Remove the extension to get the protein name to use as the PDB header
    protein_name = pdb_name.split("/")[-1][:-4].upper()
    new_pdb_name = f"{protein_name}_ensemble.pdb"

    # Open files for reading
    xyz_file = open(xyz_name, "r").readlines()
    pdb_file = open(pdb_name, "r").readlines()
    max_atom = int(pdb_file[len(pdb_file) - 3].split()[1])
    new_file = open(new_pdb_name, "w")

    atom = -1  # Start at -1 to skip the XYZ header
    model_number = 2
    new_file.write(f"{protein_name}\n")  # PDB header line
    new_file.write(f"MODEL        1\n")  # The first line will always be MODEL 1

    for line in xyz_file:
        if atom > 0:
            atom += 1
            x, y, z = line.strip("\n").split()[1:5]  # Coordinates from xyz file
            pdb_line = pdb_file[atom - 2]  # PDB is two behind the xyz
            new_file.write(
                f"{pdb_line[0:30]}{x[0:6]}  {y[0:6]}  {z[0:6]}  {pdb_line[54:80]}\n"
            )
        else:
            atom += 1
        if atom > max_atom:
            atom = -1
            new_file.write("TER\n")
            new_file.write("ENDMDL\n")
            new_file.write(f"MODEL        {str(model_number)}\n")
            model_number += 1

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Converted {xyz_name} to {new_pdb_name}.
        \tOUTPUT: Generated {new_pdb_name} in the current directory.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def clean_incomplete_xyz() -> None:
    """
    For removing incomplete frames during troublshooting.

    This is current under construction.
    I am not sure about its use cases.

    """

    start_time = time.time()  # Used to report the executation speed
    orig_file = "all_coors.xyz"
    new_file = "all_coors_clean.xyz"
    incomplete = 0  # Only used to create user status report at end

    with open(new_file, "w") as coors_file_new:
        with open(orig_file, "r") as coors_file:
            section_delim = coors_file.readline().strip()  # First line
            section = []  # Stores the lines for each section
            first_line = True  # The first line is a unique case

            for line in coors_file:
                # Write out the first line no matter what
                if first_line:
                    section.append(line)
                    first_line = False
                else:
                    # Reached the end of a section?
                    if line[: len(section_delim)] == section_delim:
                        # Check if the section has all the atoms it should
                        if len(section) == int(section_delim) + 2:
                            # Write the section out to the new file if complete
                            for line in section:
                                coors_file_new.write(line)
                        else:
                            incomplete += 1
                        # Start a new section
                        section = []
                        section.append(line)
                    else:
                        section.append(line)

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Found {incomplete} incomplete sections.
        \tOUTPUT: Generated {new_file} in the current directory.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def check_valid_resname(res) -> Tuple[str, int]:
    """
    Checks if a valid resname has been identified.

    Excepts a resname of the form e.g. Ala1, A1, Gly12, G12.
    If an incorrect resname is supplied the fuction will exit with an warning.

    Parameters
    ----------
    res : str
        Name of a residue of the form e.g. Ala1, Gly12.

    Return
    ------
    aa_name : str
        The requested amino acid's three letter code.
    aa_num : int
        The requested amino acid's position in the sequence.

    """
    # Get amino acid identifier information from the reference module
    aa_identifiers = qa.reference.get_aa_identifiers()
    # Check if one or three letter code provided by counting letters
    letter_count = sum(map(str.isalpha, res))

    if letter_count == 1:
        aa_name = res[0].upper().strip()  # clean the input
        aa_num = int(res[1:])

    if letter_count == 3 or res[:3] == "Hm1":
        aa_name = res[:3].upper().strip()  # clean the input
        aa_num = int(res[3:])

    print(f"> Reqesting amino acid {aa_name} at index {aa_num}.")

    return aa_name, aa_num


def get_res_atom_indices(res, scheme="all") -> List[int]:
    """
    For a residue get the atom indices of all atoms in the residue.

    Parameters
    ----------
    res : str
        Name of a residue of the form e.g. Ala1, Gly12.
    type :str
        The type of atom indices to retrieve e.g., all, backbone

    Returns
    -------
    residue_indices : list
        A list of all atom indices for a given residue.

    """

    # Function that gets the path of a PDB file
    pdb = get_pdb()
    # Check if the requested resname is valid
    aa_name, aa_num = check_valid_resname(res)
    # Convert the pdb to a pandas dataframe
    ppdb = PandasPdb().read_pdb(pdb).df["ATOM"]

    # Indices for all residues or for just the backbone
    residue_df = ppdb[
        (ppdb["residue_name"] == aa_name) & (ppdb["residue_number"] == aa_num)
    ]
    atom_index_list = residue_df.index.tolist()

    # Use if you only want the backbone atoms summed
    if scheme == "backbone":
        print(
            "> Retrieving only backbone indices. See qa.process.get_res_atom_indices()"
        )
        bb_atoms = ["N", "H", "C", "O"]
        backbone_df = residue_df[residue_df["atom_name"].isin(bb_atoms)]
        atom_index_list = backbone_df.index.tolist()

    if scheme != "all" and scheme != "backbone":
        raise ValueError("> ERROR: Scheme not recognized. Select all or backbone.")

    # Alert the user if the list comes out empty
    if len(atom_index_list) == 0:
        raise ValueError("> ERROR: No atom indices were found. Verify that it exists.")

    return atom_index_list


def clean_qm_jobs(first_job: int, last_job: int, step: int) -> None:
    """
    Cleans all QM jobs and checks for completion.

    We ran single points at a higher level of theory from the SQM simulations.
    Some jobs will inevitable die do to memory or convergence issues.
    It is important to check that all the jobs finished successfully.
    This script checks that all the jobs finished.
    Once it has confirmed that all jobs finished sucessfully,
    it will clean up the QM by deleting log files and scratch directories.

    Parameters
    ----------
    first_job: int
        The name of the first directory and first job e.g., 0
    last_job: int
        The name of the last directory and last job e.g., 39900
    step: int
        The step size between each single point.
    """
    start_time = time.time()  # Used to report the executation speed

    # Directory containing all replicates
    primary_dir = os.getcwd()
    replicates = sorted(glob.glob("*/"))
    total_job_count = 0  # Report to user upon job completion
    incomplete_job_count = 0  # Report to user upon job completion

    for replicate in replicates:
        os.chdir(replicate)
        # The location of the current replicate
        secondary_dir = os.getcwd()
        print(f"> Checking {secondary_dir}.")

        # A list of all job directories assuming they are named as integers
        job_dirs = [str(dir) for dir in range(first_job, last_job, step)]
        for dir in job_dirs:
            total_job_count += 1
            os.chdir(dir)
            tertiary_dir = os.getcwd()

            # Get the out file, we use glob so we can generalize to all out files
            out_name = glob.glob("*.out")
            if len(out_name) < 1:
                print(f"   > Job in {tertiary_dir} did not finish.")
            else:
                # Determine if a job finished
                with open(out_name[0], "r") as out_file:
                    lines = out_file.read().rstrip().splitlines()
                    last_line = lines[-1]
                    # The phrase Job finished is indicative of a success
                    if "Job finished" not in last_line:
                        incomplete_job_count += 1
                        print(f"   > Job in {tertiary_dir} did not finish.")

                    # The job completed, so delete extra scr directories
                    else:
                        scr_dirs = glob.glob("scr*/")
                        # Sort the scr directories by age (oldest to newest)
                        sorted_scr_dirs = sorted(
                            scr_dirs, key=os.path.getmtime, reverse=True
                        )
                        # Only keep the newest
                        # for scr_dir in sorted_scr_dirs[1:]:
                        #     shutil.rmtree(scr_dir)
                        #     print(f"   > Delete extra scratch directory: {scr_dir}")

            os.chdir(secondary_dir)
        os.chdir(primary_dir)

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Checked {total_job_count} jobs for completion.
        \tOUTPUT: Found {incomplete_job_count} incomplete or problematic jobs.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def combine_qm_charges(first_job: int, last_job: int, step: int) -> None:
    """
    Combines the charge_mull.xls files generate by TeraChem single points.

    After running periodic single points on the ab-initio MD data,
    we need to process the charge data so that it matches the SQM data.
    This code gets the charges from each single point and combines them.
    Results are stored in a tabular form.

    Parameters
    ----------
    first_job: int
        The name of the first directory and first job e.g., 0
    last_job: int
        The name of the last directory and last job e.g., 39901
    step: int
        The step size between each single point.

    """
    start_time = time.time()  # Used to report the executation speed
    new_charge_file = "all_charges.xls"
    current_charge_file = "charge_mull.xls"
    ignore = ["Analysis/"]

    # Directory containing all replicates
    primary_dir = os.getcwd()
    directories = sorted(glob.glob("*/"))
    replicates = [i for i in directories if i not in ignore]
    replicate_count = len(replicates)  # Report to user

    for replicate in replicates:
        frames = 0  # Saved to report to the user
        os.chdir(replicate)
        # The location of the current qm job that we are appending
        secondary_dir = os.getcwd()
        print(f"   > Adding { secondary_dir}")

        # Create a new file where we will store the combined charges
        first_charges_file = True  # We need the title line but only once

        if os.path.exists(new_charge_file):
            os.remove(new_charge_file)  # Since appending remove old version
            print(f"      > Deleting old {secondary_dir}/{new_charge_file}.")
        with open(new_charge_file, "a") as combined_charges_file:
            # A list of all job directories assuming they are named as integers
            job_dirs = [str(dir) for dir in range(first_job, last_job, step)]

            # Change into one of the QM job directories
            for index, dir in enumerate(job_dirs):
                os.chdir(dir)
                tertiary_dir = os.getcwd()
                os.chdir("scr")
                # Open an individual charge file from a QM single point
                atom_column = []
                charge_column = []

                # Open one of the QM charge single point files
                with open(current_charge_file, "r") as charges_file:
                    # Separate the atom and charge information
                    for line in charges_file:
                        clean_line = line.strip().split("\t")
                        charge_column.append(clean_line[1])
                        atom_column.append(clean_line[0])

                # Join the data and separate it with tabs
                charge_line = "\t".join(charge_column)

                # For some reason, TeraChem indexes at 0 with SQM,
                # and 1 with QM so we change the index to start at 1
                atoms_line_reindex = []
                for atom in atom_column:
                    atom_list = atom.split()
                    atom_list[0] = str(int(atom_list[0]) - 1)
                    x = " ".join(atom_list)
                    atoms_line_reindex.append(x)
                atom_line = "\t".join(atoms_line_reindex)

                # Append the data to the combined charges data file
                # We only add the header line once
                if first_charges_file:
                    combined_charges_file.write(f"{atom_line}\n")
                    combined_charges_file.write(f"{charge_line}\n")
                    frames += 1
                    first_charges_file = False
                # Skip the header if it has already been added
                else:
                    if "nan" in charge_line:
                        print(f"      > Found nan values in {index * 100}!!")
                    combined_charges_file.write(f"{charge_line}\n")
                    frames += 1

                os.chdir(secondary_dir)
        print(f"      > Combined {frames} frames.")
        os.chdir(primary_dir)

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Combined charges across {replicate_count} replicates.
        \tOUTPUT: Generated {new_charge_file} in the current directory.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def combine_qm_replicates() -> None:
    """
    Combine the all_charges.xls files for replicates into a master charge file.

    The combined file contains a single header with atom numbers as columns.
    Each row represents a new charge instance.
    The first column indicates which replicate the charge came from.

    """
    start_time = time.time()  # Used to report the executation speed
    charge_file = "all_charges.xls"
    ignore = ["Analysis/"]

    # Directory containing all replicates
    primary_dir = os.getcwd()
    directories = sorted(glob.glob("*/"))
    replicates = [i for i in directories if i not in ignore]
    replicate_count = len(replicates)  # Report to user

    # Remove any old version because we are appending
    if os.path.exists(charge_file):
        os.remove(charge_file)
        print(f"      > Deleting old {charge_file}.")

    # Create a new file to save charges
    with open(charge_file, "a") as new_charge_file:
        header_written = False
        for replicate in replicates:
            # There will always be an Analysis folder
            os.chdir(replicate)
            secondary_dir = os.getcwd()
            print(f"   > Adding {secondary_dir}")

            # Get the replicate number from the folder name
            replicate_number = os.path.basename(os.path.normpath(secondary_dir))

            # Add the header for the first replicate
            with open(charge_file, "r") as current_charge_file:
                for index, line in enumerate(current_charge_file):
                    if index == 0:
                        if not header_written:
                            new_charge_file.writelines(line.strip() + "\treplicate\n")
                            header_written = True
                        continue
                    elif "nan" in line:
                        print(f"      > Found nan values in {secondary_dir}.")
                    else:
                        new_charge_file.writelines(line.strip() + "\t" + replicate_number + "\n")

            os.chdir(primary_dir)

    total_time = round(time.time() - start_time, 3)  # Seconds to run the function
    print(
        f"""
        \t----------------------------ALL RUNS END----------------------------
        \tRESULT: Combined charges across {replicate_count} replicates.
        \tOUTPUT: Generated {charge_file} in the current directory.
        \tTIME: Total execution time: {total_time} seconds.
        \t--------------------------------------------------------------------\n
        """
    )


def string_to_list(str_list: List[str]) -> List[List[int]]:
    """
    Converts a list of numerical strings to a list of lists of numbers.

    It takes a list of numerical strings so that it can process them in bulk.

    Examples
    --------
    ["1-4,6,8-10", "1-3"] -> [[1,2,3,4,6,8,9,10],[1,2,3]]

    """
    number_list = []
    for number_string in str_list:
        segments = number_string.split(",")

        sub_list = []

        for segment in segments:
            if "-" in segment:
                start, end = map(int, segment.split("-"))
                sub_list.extend(range(start, end + 1))
            else:
                sub_list.append(int(segment))

        number_list.append(sub_list)

    return number_list



def simple_xyz_combine():
    """
    Takes all xyz molecular structure files in the current directory
    and combines them to create a single xyz trajectory.

    Notes
    -----
    The output xyz trajectory file will have no additional white space
    and will have each xyz concatenated after the next.
    The output xyz will be called combined.xyz
    """

    # Get a list of all xyz files in the current directory
    xyz_files = glob.glob("*.xyz")

    # Sort the files based on the numerical part of the filename
    xyz_files.sort(key=lambda x: int(os.path.splitext(x)[0]))

    # Create the output directory if it doesn't exist
    output_dir = "../Analysis/3_centroid"
    os.makedirs(output_dir, exist_ok=True)

    # Create the full output file path
    output_file_path = os.path.join(output_dir, "combined.xyz")

    # Open the output file in write mode
    with open(output_file_path, "w") as outfile:
        # Loop through each file
        for file in xyz_files:
            # Open each file in read mode
            with open(file, "r") as infile:
                # Read the contents of the file
                contents = infile.read()

                # Write the contents to the output file
                outfile.write(contents)

    print(f"   > All .xyz files have been combined into {output_file_path}")


if __name__ == "__main__":
    # Run the command-line interface when this script is executed
    simple_xyz_combine()