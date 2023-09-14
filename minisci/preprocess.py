"""
© 2023, ETH Zurich
"""
import h5py
import numpy as np
import pandas as pd
import torch
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from scipy.spatial.distance import pdist, squareform
from tqdm import tqdm

from minisci.utils import (
    AROMATOCITY_DICT,
    ATOMTYPE_DICT,
    DATASET_NAME,
    HYBRIDISATION_DICT,
    IS_RING_DICT,
    get_dict_for_embedding,
)


def get_fp_from_smi(smi):
    """Get ECFP from SMILES"""
    mol_no_Hs = Chem.MolFromSmiles(smi)
    mol = Chem.AddHs(mol_no_Hs)

    return np.array(rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, 2, nBits=256))


def get_3dG_from_smi(smi, randomSeed):
    # get mol objects from smiles
    mol_no_Hs = Chem.MolFromSmiles(smi)
    mol = Chem.AddHs(mol_no_Hs)

    atomids = []
    is_ring = []
    hyb = []
    arom = []
    crds_3d = []
    tokeep = []

    AllChem.EmbedMolecule(mol, randomSeed)  # 0xf00d
    AllChem.UFFOptimizeMolecule(mol)

    for idx, i in enumerate(mol.GetAtoms()):
        atomids.append(ATOMTYPE_DICT[i.GetSymbol()])
        is_ring.append(IS_RING_DICT[str(i.IsInRing())])
        hyb.append(HYBRIDISATION_DICT[str(i.GetHybridization())])
        arom.append(AROMATOCITY_DICT[str(i.GetIsAromatic())])
        crds_3d.append(list(mol.GetConformer().GetAtomPosition(idx)))
        if (
            (ATOMTYPE_DICT[i.GetSymbol()] == 1)
            and (IS_RING_DICT[str(i.IsInRing())] == 0)
            and (AROMATOCITY_DICT[str(i.GetIsAromatic())] == 0)
            and (HYBRIDISATION_DICT[str(i.GetHybridization())] == 1)
        ):
            tokeep.append(1)
        else:
            tokeep.append(0)

    atomids = np.array(atomids)
    is_ring = np.array(is_ring)
    hyb = np.array(hyb)
    arom = np.array(arom)
    crds_3d = np.array(crds_3d)
    tokeep = np.array(tokeep)

    # edges for covalent bonds in sdf file
    edge_dir1 = []
    edge_dir2 = []
    for idx, bond in enumerate(mol.GetBonds()):
        a2 = bond.GetEndAtomIdx()
        a1 = bond.GetBeginAtomIdx()
        edge_dir1.append(a1)
        edge_dir1.append(a2)
        edge_dir2.append(a2)
        edge_dir2.append(a1)

    edge_2d = torch.from_numpy(np.array([edge_dir1, edge_dir2]))

    # Get edges for 3d graph
    distance_matrix = squareform(pdist(crds_3d))
    np.fill_diagonal(distance_matrix, float("inf"))  # to remove self-loops
    edge_3d = torch.from_numpy(np.vstack(np.where(distance_matrix <= 4)))

    return (
        atomids,
        is_ring,
        hyb,
        arom,
        edge_2d,
        edge_3d,
        crds_3d,
        tokeep,
    )


if __name__ == "__main__":
    # read csv id
    df = pd.read_csv(f"data/{DATASET_NAME}.tsv", sep="\t", encoding="unicode_escape")

    rxn_id = list(df["rxn_id"])
    temperature_degC = list(df["temperature_deg_c"])
    time_h = list(df["time_h"])
    atmosphere = list(df["atmosphere"])
    atmosphere = [str(x) for x in atmosphere]
    scale_mol = list(df["scale_umol"])
    concentration_moll = list(df["concentration_mmol_l"])
    startingmat_1_smiles = list(df["startingmat_1_smiles"])
    startingmat_1_smiles = [str(x) for x in startingmat_1_smiles]
    startingmat_2_smiles = list(df["startingmat_2_smiles"])
    startingmat_2_smiles = [str(x) for x in startingmat_2_smiles]
    startingmat_2_eq = list(df["startingmat_2_eq"])
    reagent_1_smiles = list(df["reagent_1_smiles"])
    reagent_1_smiles = [str(x) for x in reagent_1_smiles]
    reagent_1_eq = list(df["reagent_1_eq"])
    catalyst_1_smiles = list(df["catalyst_1_smiles"])
    catalyst_1_smiles = [str(x) for x in catalyst_1_smiles]
    catalyst_1_eq = list(df["catalyst_1_eq"])
    additive_1_smiles = list(df["additive_1_smiles"])
    additive_1_smiles = [str(x) for x in additive_1_smiles]
    additive_1_eq = list(df["additive_1_eq"])
    solvent_1_smiles = list(df["solvent_1_smiles"])
    solvent_1_smiles = [str(x) for x in solvent_1_smiles]
    solvent_1_fraction = list(df["solvent_1_fraction"])
    solvent_2_smiles = list(df["solvent_2_smiles"])
    solvent_2_smiles = [str(x) for x in solvent_2_smiles]
    solvent_2_fraction = list(df["solvent_2_fraction"])

    product_mono = list(df["product_mono"])
    product_di = list(df["product_di"])
    product_non = list(df["product_non"])
    binary = list(df["binary"])

    print(f"Number of individual reactions: {len(rxn_id)}")

    rea_dict = get_dict_for_embedding(reagent_1_smiles)
    so1_dict = get_dict_for_embedding(solvent_1_smiles)
    so2_dict = get_dict_for_embedding(solvent_2_smiles)
    cat_dict = get_dict_for_embedding(catalyst_1_smiles)
    add_dict = get_dict_for_embedding(additive_1_smiles)
    atm_dict = get_dict_for_embedding(atmosphere)
    print(
        "Distinct reagent and solvent types (should be >1 each): ",
        "\n",
        "Reagent:",
        rea_dict,
        "\n",
        "Solvent 1:",
        so1_dict,
        "\n",
        "Solvent 2:",
        so2_dict,
        "\n",
        "Catalyst:",
        cat_dict,
        "Additives:",
        add_dict,
        "\n",
        "Atmosphere:",
        atm_dict,
    )
    product_all = [float(product_mono[i] + product_di[i]) for i, x in enumerate(product_mono)]

    cond_dicts = [rea_dict, so1_dict, so2_dict, cat_dict, add_dict, atm_dict]
    torch.save(cond_dicts, f"data/lsf_rxn_cond_dicts_{DATASET_NAME}.pt")

    # Get unique substrates
    startingmat_1_unique = list(set(startingmat_1_smiles))
    startingmat_2_unique = list(set(startingmat_2_smiles))
    print(
        f"Number of unique reactions: {len(rxn_id)} \nNumber of substrates: {len(startingmat_1_unique)}, \nNumber of carboxylic acids: {len(startingmat_2_unique)}"
    )

    # Get the rxn keys for the two starting materials
    rxn_smi_dict = {}
    for i, rxn in enumerate(rxn_id):
        rxn_smi_dict[rxn] = [startingmat_1_smiles[i], startingmat_2_smiles[i]]

    torch.save(rxn_smi_dict, f"data/rxn_smi_dict_{DATASET_NAME}.pt")

    # Get 3D graph data
    print(f"\nGenerating 3D conformers for {len(startingmat_1_unique)} substrates and saving them into h5 format:")

    with h5py.File(f"data/lsf_rxn_substrate_{DATASET_NAME}.h5", "w") as lsf_container1:
        for smi in tqdm(startingmat_1_unique):
            # smi = wash_smiles(smi)

            (
                atom_id_1_a,
                ring_id_1_a,
                hybr_id_1_a,
                arom_id_1_a,
                edge_2d_1_a,
                edge_3d_1_a,
                crds_3d_1_a,
                to_keep_1_a,
            ) = get_3dG_from_smi(smi, 0xF00A)

            (
                atom_id_1_b,
                ring_id_1_b,
                hybr_id_1_b,
                arom_id_1_b,
                edge_2d_1_b,
                edge_3d_1_b,
                crds_3d_1_b,
                to_keep_1_b,
            ) = get_3dG_from_smi(smi, 0xF00B)

            (
                atom_id_1_c,
                ring_id_1_c,
                hybr_id_1_c,
                arom_id_1_c,
                edge_2d_1_c,
                edge_3d_1_c,
                crds_3d_1_c,
                to_keep_1_c,
            ) = get_3dG_from_smi(smi, 0xF00C)

            (
                atom_id_1_d,
                ring_id_1_d,
                hybr_id_1_d,
                arom_id_1_d,
                edge_2d_1_d,
                edge_3d_1_d,
                crds_3d_1_d,
                to_keep_1_d,
            ) = get_3dG_from_smi(smi, 0xF00D)

            (
                atom_id_1_e,
                ring_id_1_e,
                hybr_id_1_e,
                arom_id_1_e,
                edge_2d_1_e,
                edge_3d_1_e,
                crds_3d_1_e,
                to_keep_1_e,
            ) = get_3dG_from_smi(smi, 0xF00E)

            # Substrate ID
            lsf_container1.create_group(smi)

            # Molecule
            lsf_container1[smi].create_dataset("atom_id_1_a", data=atom_id_1_a)
            lsf_container1[smi].create_dataset("ring_id_1_a", data=ring_id_1_a)
            lsf_container1[smi].create_dataset("hybr_id_1_a", data=hybr_id_1_a)
            lsf_container1[smi].create_dataset("arom_id_1_a", data=arom_id_1_a)
            lsf_container1[smi].create_dataset("edge_2d_1_a", data=edge_2d_1_a)
            lsf_container1[smi].create_dataset("edge_3d_1_a", data=edge_3d_1_a)
            lsf_container1[smi].create_dataset("crds_3d_1_a", data=crds_3d_1_a)
            lsf_container1[smi].create_dataset("to_keep_1_a", data=to_keep_1_a)

            lsf_container1[smi].create_dataset("atom_id_1_b", data=atom_id_1_b)
            lsf_container1[smi].create_dataset("ring_id_1_b", data=ring_id_1_b)
            lsf_container1[smi].create_dataset("hybr_id_1_b", data=hybr_id_1_b)
            lsf_container1[smi].create_dataset("arom_id_1_b", data=arom_id_1_b)
            lsf_container1[smi].create_dataset("edge_2d_1_b", data=edge_2d_1_b)
            lsf_container1[smi].create_dataset("edge_3d_1_b", data=edge_3d_1_b)
            lsf_container1[smi].create_dataset("crds_3d_1_b", data=crds_3d_1_b)
            lsf_container1[smi].create_dataset("to_keep_1_b", data=to_keep_1_b)

            lsf_container1[smi].create_dataset("atom_id_1_c", data=atom_id_1_c)
            lsf_container1[smi].create_dataset("ring_id_1_c", data=ring_id_1_c)
            lsf_container1[smi].create_dataset("hybr_id_1_c", data=hybr_id_1_c)
            lsf_container1[smi].create_dataset("arom_id_1_c", data=arom_id_1_c)
            lsf_container1[smi].create_dataset("edge_2d_1_c", data=edge_2d_1_c)
            lsf_container1[smi].create_dataset("edge_3d_1_c", data=edge_3d_1_c)
            lsf_container1[smi].create_dataset("crds_3d_1_c", data=crds_3d_1_c)
            lsf_container1[smi].create_dataset("to_keep_1_c", data=to_keep_1_c)

            lsf_container1[smi].create_dataset("atom_id_1_d", data=atom_id_1_d)
            lsf_container1[smi].create_dataset("ring_id_1_d", data=ring_id_1_d)
            lsf_container1[smi].create_dataset("hybr_id_1_d", data=hybr_id_1_d)
            lsf_container1[smi].create_dataset("arom_id_1_d", data=arom_id_1_d)
            lsf_container1[smi].create_dataset("edge_2d_1_d", data=edge_2d_1_d)
            lsf_container1[smi].create_dataset("edge_3d_1_d", data=edge_3d_1_d)
            lsf_container1[smi].create_dataset("crds_3d_1_d", data=crds_3d_1_d)
            lsf_container1[smi].create_dataset("to_keep_1_d", data=to_keep_1_d)

            lsf_container1[smi].create_dataset("atom_id_1_e", data=atom_id_1_e)
            lsf_container1[smi].create_dataset("ring_id_1_e", data=ring_id_1_e)
            lsf_container1[smi].create_dataset("hybr_id_1_e", data=hybr_id_1_e)
            lsf_container1[smi].create_dataset("arom_id_1_e", data=arom_id_1_e)
            lsf_container1[smi].create_dataset("edge_2d_1_e", data=edge_2d_1_e)
            lsf_container1[smi].create_dataset("edge_3d_1_e", data=edge_3d_1_e)
            lsf_container1[smi].create_dataset("crds_3d_1_e", data=crds_3d_1_e)
            lsf_container1[smi].create_dataset("to_keep_1_e", data=to_keep_1_e)

    h5f1 = h5py.File(f"data/lsf_rxn_substrate_{DATASET_NAME}.h5")
    print(f"Successfully transformed {len(list(h5f1.keys()))} substrates")

    print(
        f"\nGenerating 3D conformers for {len(startingmat_2_unique)} carboxylic acids and saving them into h5 format:"
    )

    with h5py.File(f"data/lsf_rxn_carbacids_{DATASET_NAME}.h5", "w") as lsf_container2:
        for smi in tqdm(startingmat_2_unique):
            # smi = wash_smiles(smi)
            (
                atom_id_2_a,
                ring_id_2_a,
                hybr_id_2_a,
                arom_id_2_a,
                edge_2d_2_a,
                edge_3d_2_a,
                crds_3d_2_a,
                to_keep_2_a,
            ) = get_3dG_from_smi(smi, 0xF00A)

            (
                atom_id_2_b,
                ring_id_2_b,
                hybr_id_2_b,
                arom_id_2_b,
                edge_2d_2_b,
                edge_3d_2_b,
                crds_3d_2_b,
                to_keep_2_b,
            ) = get_3dG_from_smi(smi, 0xF00B)

            (
                atom_id_2_c,
                ring_id_2_c,
                hybr_id_2_c,
                arom_id_2_c,
                edge_2d_2_c,
                edge_3d_2_c,
                crds_3d_2_c,
                to_keep_2_c,
            ) = get_3dG_from_smi(smi, 0xF00C)

            (
                atom_id_2_d,
                ring_id_2_d,
                hybr_id_2_d,
                arom_id_2_d,
                edge_2d_2_d,
                edge_3d_2_d,
                crds_3d_2_d,
                to_keep_2_d,
            ) = get_3dG_from_smi(smi, 0xF00D)

            (
                atom_id_2_e,
                ring_id_2_e,
                hybr_id_2_e,
                arom_id_2_e,
                edge_2d_2_e,
                edge_3d_2_e,
                crds_3d_2_e,
                to_keep_2_e,
            ) = get_3dG_from_smi(smi, 0xF00E)

            # Substrate ID
            lsf_container2.create_group(smi)

            # Molecule
            lsf_container2[smi].create_dataset("atom_id_2_a", data=atom_id_2_a)
            lsf_container2[smi].create_dataset("ring_id_2_a", data=ring_id_2_a)
            lsf_container2[smi].create_dataset("hybr_id_2_a", data=hybr_id_2_a)
            lsf_container2[smi].create_dataset("arom_id_2_a", data=arom_id_2_a)
            lsf_container2[smi].create_dataset("edge_2d_2_a", data=edge_2d_2_a)
            lsf_container2[smi].create_dataset("edge_3d_2_a", data=edge_3d_2_a)
            lsf_container2[smi].create_dataset("crds_3d_2_a", data=crds_3d_2_a)

            lsf_container2[smi].create_dataset("atom_id_2_b", data=atom_id_2_b)
            lsf_container2[smi].create_dataset("ring_id_2_b", data=ring_id_2_b)
            lsf_container2[smi].create_dataset("hybr_id_2_b", data=hybr_id_2_b)
            lsf_container2[smi].create_dataset("arom_id_2_b", data=arom_id_2_b)
            lsf_container2[smi].create_dataset("edge_2d_2_b", data=edge_2d_2_b)
            lsf_container2[smi].create_dataset("edge_3d_2_b", data=edge_3d_2_b)
            lsf_container2[smi].create_dataset("crds_3d_2_b", data=crds_3d_2_b)

            lsf_container2[smi].create_dataset("atom_id_2_c", data=atom_id_2_c)
            lsf_container2[smi].create_dataset("ring_id_2_c", data=ring_id_2_c)
            lsf_container2[smi].create_dataset("hybr_id_2_c", data=hybr_id_2_c)
            lsf_container2[smi].create_dataset("arom_id_2_c", data=arom_id_2_c)
            lsf_container2[smi].create_dataset("edge_2d_2_c", data=edge_2d_2_c)
            lsf_container2[smi].create_dataset("edge_3d_2_c", data=edge_3d_2_c)
            lsf_container2[smi].create_dataset("crds_3d_2_c", data=crds_3d_2_c)

            lsf_container2[smi].create_dataset("atom_id_2_d", data=atom_id_2_d)
            lsf_container2[smi].create_dataset("ring_id_2_d", data=ring_id_2_d)
            lsf_container2[smi].create_dataset("hybr_id_2_d", data=hybr_id_2_d)
            lsf_container2[smi].create_dataset("arom_id_2_d", data=arom_id_2_d)
            lsf_container2[smi].create_dataset("edge_2d_2_d", data=edge_2d_2_d)
            lsf_container2[smi].create_dataset("edge_3d_2_d", data=edge_3d_2_d)
            lsf_container2[smi].create_dataset("crds_3d_2_d", data=crds_3d_2_d)

            lsf_container2[smi].create_dataset("atom_id_2_e", data=atom_id_2_e)
            lsf_container2[smi].create_dataset("ring_id_2_e", data=ring_id_2_e)
            lsf_container2[smi].create_dataset("hybr_id_2_e", data=hybr_id_2_e)
            lsf_container2[smi].create_dataset("arom_id_2_e", data=arom_id_2_e)
            lsf_container2[smi].create_dataset("edge_2d_2_e", data=edge_2d_2_e)
            lsf_container2[smi].create_dataset("edge_3d_2_e", data=edge_3d_2_e)
            lsf_container2[smi].create_dataset("crds_3d_2_e", data=crds_3d_2_e)

    h5f2 = h5py.File(f"data/lsf_rxn_carbacids_{DATASET_NAME}.h5")
    print(f"Successfully transformed {len(list(h5f2.keys()))} carboxylic acids")

    print(f"\nTransforming {len(rxn_id)} reactions into h5 format")

    with h5py.File(f"data/lsf_rxn_conditions_{DATASET_NAME}.h5", "w") as lsf_container:
        for idx, rxn_key in enumerate(tqdm(rxn_id)):
            smi1 = startingmat_1_smiles[idx]
            smi2 = startingmat_2_smiles[idx]
            rgt_eq = float(reagent_1_eq[idx])
            sm2_eq = float(startingmat_2_eq[idx])
            conc_m = float(concentration_moll[idx])
            tmp_de = float(temperature_degC[idx])
            hours_ = float(time_h[idx])
            scale_ = float(scale_mol[idx])
            cat_eq = float(catalyst_1_eq[idx])
            add_eq = float(additive_1_eq[idx])
            sol_f1 = float(solvent_1_fraction[idx])
            sol_f2 = float(solvent_2_fraction[idx])

            # print(rxn_key, smi1, smi2, rgt_eq, sm2_eq, conc_m)
            rea_id = int(rea_dict[reagent_1_smiles[idx]])
            so1_id = int(so1_dict[solvent_1_smiles[idx]])
            so2_id = int(so2_dict[solvent_2_smiles[idx]])
            cat_id = int(cat_dict[catalyst_1_smiles[idx]])
            add_id = int(add_dict[additive_1_smiles[idx]])
            atm_id = int(atm_dict[atmosphere[idx]])

            ecfp4_2_1 = get_fp_from_smi(smi1)
            ecfp4_2_2 = get_fp_from_smi(smi2)

            # print(rea_id, so1_id, so2_id, cat_id, add_id, atm_id)

            # Create group in h5 for this ids
            lsf_container.create_group(rxn_key)

            # Molecule ECFP
            lsf_container[rxn_key].create_dataset("ecfp4_2_1", data=[ecfp4_2_1])
            lsf_container[rxn_key].create_dataset("ecfp4_2_2", data=[ecfp4_2_2])

            # Conditions
            lsf_container[rxn_key].create_dataset("rgt_eq", data=[rgt_eq])
            lsf_container[rxn_key].create_dataset("sm2_eq", data=[sm2_eq])
            lsf_container[rxn_key].create_dataset("conc_m", data=[conc_m])
            lsf_container[rxn_key].create_dataset("tmp_de", data=[tmp_de])
            lsf_container[rxn_key].create_dataset("hours_", data=[hours_])
            lsf_container[rxn_key].create_dataset("scale_", data=[scale_])
            lsf_container[rxn_key].create_dataset("cat_eq", data=[cat_eq])
            lsf_container[rxn_key].create_dataset("add_eq", data=[add_eq])
            lsf_container[rxn_key].create_dataset("sol_f1", data=[sol_f1])
            lsf_container[rxn_key].create_dataset("sol_f2", data=[sol_f2])

            lsf_container[rxn_key].create_dataset("rea_id", data=[rea_id])
            lsf_container[rxn_key].create_dataset("so1_id", data=[so1_id])
            lsf_container[rxn_key].create_dataset("so2_id", data=[so2_id])
            lsf_container[rxn_key].create_dataset("cat_id", data=[cat_id])
            lsf_container[rxn_key].create_dataset("add_id", data=[add_id])
            lsf_container[rxn_key].create_dataset("atm_id", data=[atm_id])

            # Traget
            lsf_container[rxn_key].create_dataset("trg_yld", data=[product_all[idx]])
            lsf_container[rxn_key].create_dataset("trg_bin", data=[binary[idx]])

    h5f = h5py.File(f"data/lsf_rxn_conditions_{DATASET_NAME}.h5")
    print(f"Successfully transformed {len(list(h5f.keys()))} reaction")
