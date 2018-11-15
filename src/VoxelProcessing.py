import numpy as np
import os
from scipy import sparse
from scipy import ndimage
import subprocess

class VoxelProcessing:

    def __init__(self, filename, dimension, structure):
        '''
        Parameters
        ----------
        filename  : str
                    Name of the Input .npy file
        dimension : list
                    list contain three value which represents the dimension
                    of the 3D array
        structure : numpy array
                    Structuring element used for the Morphological Operation
        '''
        self.x_dim = dimension[0]
        self.y_dim = dimension[1]
        self.z_dim = dimension[2]
        self.my_list = []
        self.add_mem()
        self.struct_element = structure
        self.arr_map = np.load(filename, mmap_mode="r")

    def get_CRS_mem_size(self, CRS):
        '''
        Parameters
        ----------
        CRS : array_like
              sparse matrix with Non-zero stored elements
              in compressed sparse Row format
        Returns
        -------
        float
            Size of the CRS object
        '''
        total = CRS.data.nbytes + CRS.indptr.nbytes + CRS.indices.nbytes
        mem =  total / 1000000000
        print("CRS Memory size = ", mem, "Gb")

    def convert_to_2d(self):
        '''
        Returns
        -------
        array_like
                Transforms (M x N x 3) into an array (3 x (MxN))
        '''
        arr_2d = self.arr_map.reshape((self.arr_map.shape[0]*
                             self.arr_map.shape[1]), self.arr_map.shape[2])
        arr_2d = arr_2d.transpose()
        return arr_2d

    def compressed_storage(self, arr_2d):
        '''
        Parameters:
        ----------
        arr_2d : array_like
                 2 dimensional array

        Save a sparse matrix to a file using .npz format
        '''
        directory = 'compressed'
        output = 'output'
        CRS = sparse.csr_matrix(arr_2d, dtype='float32')
        if not os.path.exists(directory):
            os.makedirs(directory)
        if not os.path.exists(output):
            os.makedirs(output)
        sparse.save_npz("compressed/CRS.npz", CRS)

    def load_compressed(self):
        '''
        Returns:
        --------
        Compressed Sparse Row matrix
                Returns sparse matrix with Non-zero stored
                elements in Compressed Sparse Row format
        '''
        filename = "compressed/CRS.npz"
        try:
            CRS_RAM = open(filename, 'r')
        except:
            print('Cannot open', filename)
            return 0
        else:
            CRS_RAM = sparse.load_npz(filename)
            self.add_mem()
            return CRS_RAM

    def Morphology(self, CRS, n_blocks, operation):
        '''
        Parameters:
        -----------
        CRS      : array_like
                   sparse matrix with Non-zero stored elements
                   in compressed sparse Row format
        n_blocks : int
                   Split an array into n_blocks of sub-arrays
        operation : str
                    Morphological Operation
        '''
        start_index = 0
        fake_ghost = 3
        splits = (self.arr_map.shape[0]*
                    self.arr_map.shape[1])//(self.y_dim*10)
        x = CRS.shape[1] // (splits*10)
        print(splits, x, self.arr_map.shape[0], self.arr_map.shape[1])
        end_index = int(CRS.shape[1] / n_blocks) + (x * fake_ghost)
        jump = int(CRS.shape[1] / n_blocks)
        self.f_handle = open('output/binary', 'wb')
        self.add_mem()

        if n_blocks == 1:
              start_index = 0
              end_index = CRS.shape[1]

        for i in range(0, n_blocks):
            block_2d = CRS[:,start_index:end_index].toarray()
            self.add_mem()
            block_2d = block_2d.T
            start_index = end_index - (x * fake_ghost * 2)
            if i == n_blocks -2:
               end_index = end_index + jump - x
            else:
                end_index = end_index + jump
            self.convert_to_3d(i, block_2d, operation, n_blocks, fake_ghost)
        self.f_handle.close()

    def convert_to_3d(self, i, block_2d, operation, n_blocks, fake_ghost):
        '''
        Parameters:
        i          : int
                     block number
        blocks_2d  : array_like
                     sub-array
        operation  : str
                     Morphological Operation
        n_blocks   : int
                     Total no of blocks
        fake_ghost : int
                     No of layers of ghost cells
        '''

        n_splits = self.x_dim // n_blocks
        if n_blocks != 1:
                if i == 0 or i == n_blocks -1:
                        n_splits += 1 * fake_ghost
                else:
                        n_splits += 2 * fake_ghost

        # 2d block i reshape to 3d
        block_3d = block_2d.reshape(n_splits, self.y_dim, self.z_dim)
        self.add_mem()
        if operation == 'grey_dilation':
            print("Performing Dilation on block ", i)
            self.block_grey_dilation(block_3d, i, self.struct_element,
                                n_blocks, n_splits, fake_ghost)
        if operation == 'grey_erosion':
            print("Performing Erosion on block ", i)
            self.block_grey_erosion(block_3d, i, self.struct_element,
                                    n_blocks, n_splits, fake_ghost)

    def block_grey_dilation(self, block_3d, i, struct_element,
                       n_blocks, n_splits, fake_ghost):

        dilated = ndimage.grey_dilation(block_3d, structure=struct_element)
        self.add_mem()
        if n_blocks != 1:
                trimmed = self.trim_ghostCells(dilated, i, n_blocks, n_splits, fake_ghost)
                trimmed.tofile(self.f_handle)
                self.add_mem()
                print("Block Shape = ", trimmed.shape)
        else:
                dilated.tofile(self.f_handle)

    def block_grey_erosion(self, block_3d, i, struct_element,
                       n_blocks, n_splits, fake_ghost):

        eroded = ndimage.grey_erosion(block_3d, structure=struct_element)
        self.add_mem()
        if n_blocks != 1:
                trimmed = self.trim_ghostCells(eroded, i, n_blocks, n_splits, fake_ghost)
                trimmed.tofile(self.f_handle)
                self.add_mem()
                print("Block Shape = ", trimmed.shape)
        else:
                dilated.tofile(self.f_handle)

    def trim_ghostCells(self, block_3d, i, n_blocks, n_splits, fake_ghost):
        '''
        Parameters:
        -----------
        block_3d   : array_like
                     sub-array of size (n_splits x self.y x self.z)
        i          : int
                     sub-array block number
        n_blocks   : int
                     Total no of blocks
        n_splits   : int
                     z axis dimension length
        fake_ghost : int
                     No of layers of ghost cells
        Returns:
        --------
        array_like
                ghost cella are trimmed and sliced
                array is returned
        '''
        if i == 0:
            block_3d = block_3d[0:n_splits-1*fake_ghost,:,:]
        elif i == n_blocks - 1:
            block_3d = block_3d[1*fake_ghost:n_splits,:,:]
        else:
            block_3d = block_3d[1*fake_ghost:n_splits-1*fake_ghost,:,:]
        self.add_mem()
        return block_3d

    def merge_blocks(self):
        '''
        Contiguous 3d blocks are merged
        and saved to a file
        '''
        filename = "output/binary"
        output_filename = "output/Merged.npy"
        try:
            merging = open(filename, 'r')
        except:
            print('Cannot open', filename)
            return 0
        else:
            merging = np.memmap(filename, dtype=np.float32,
                                mode='r', shape=(self.x_dim,self.y_dim,self.z_dim))
            self.add_mem()
            np.save(output_filename, merging)
            self.add_mem()
            print()
            print("Blocks successfully merged to ", output_filename)

    def add_mem(self):
        '''
        Adds the current free memory to a list
        '''
        cmd = "free -m" + "|" +  "awk '{ print $4 }'" + "|" + "sed -n 3p"
        output = subprocess.getstatusoutput(cmd)
        self.my_list.append(int(output[1]))

    def print_memory_usage(self):
        l = len(self.my_list)
        total = sum(self.my_list[1:l])
        avg = total //(l - 1)
        print("Average Memory Usage = ", self.my_list[0] - avg, " MB")
        print()
