import numpy as np
import pandas as pd

from sklearn.preprocessing import PowerTransformer
from scipy.stats import skew, kurtosis, boxcox, yeojohnson

from scipy.special import inv_boxcox
from numpy import expm1, sqrt, square, log1p

from scipy.spatial import cKDTree

import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask as rio_mask

import os
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape, mapping
import geopandas as gpd

import geopandas as gpd
from shapely.geometry import Point
from shapely.geometry import box
import fiona

from matplotlib import pyplot as plt
import seaborn as sns
import re

from scipy.spatial.distance import pdist, squareform
from skgstat import Variogram

from sklearn.preprocessing import FunctionTransformer, PowerTransformer
from sklearn.compose import ColumnTransformer

import os
import shutil
from PyPDF2 import PdfMerger

def resample_raster(input_path, output_path, scale, resampling_method=Resampling.bilinear):
    """
    Resample a raster dataset to a different resolution.

    Parameters:
    input_path (str): Path to the input raster file.
    output_path (str): Path to save the resampled raster file.
    scale (float): Resampling scale factor. Values <1 will downsample, values >1 will upsample.
    resampling_method (rasterio.enums.Resampling, optional): The resampling method to use.
        Default is Resampling.bilinear. Other options include Resampling.nearest, Resampling.cubic, etc.

    Returns:
    None
    """
    with rasterio.open(input_path) as dataset:
        # Calculate the new dimensions
        new_height = int(dataset.height * scale)
        new_width = int(dataset.width * scale)

        # Perform the resampling
        data = dataset.read(
            out_shape=(
                dataset.count,
                new_height,
                new_width
            ),
            resampling=resampling_method
        )

        # Update the transform for the new dimensions
        transform = dataset.transform * dataset.transform.scale(
            (dataset.width / new_width),
            (dataset.height / new_height)
        )

        # Write the resampled raster to a new file
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=new_height,
            width=new_width,
            count=dataset.count,
            dtype=data.dtype,
            crs=dataset.crs,
            transform=transform,
        ) as dst:
            dst.write(data)


def exclude_zero_coordinates(gdf):
    """
    Exclude observations with (0, 0) coordinates from a GeoDataFrame.

    Parameters:
    gdf (GeoDataFrame): Input GeoDataFrame.

    Returns:
    GeoDataFrame: Filtered GeoDataFrame with observations having (0, 0) coordinates excluded.
    """
    # Ensure the geometries are of the correct type (Point)
    gdf = gdf[gdf.geometry.type == 'Point']
    
    # Filter out rows with (0, 0) coordinates
    filtered_gdf = gdf[~((gdf.geometry.x == 0) & (gdf.geometry.y == 0))]

    return filtered_gdf


import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy
from shapely.geometry import box
import geopandas as gpd

def raster_to_gdf(raster_path):
    """
    Convert a raster file to a GeoDataFrame with each band as a column and coordinates as geometry,
    excluding cells where all bands are NaN. The geometry will be squares forming a grid.

    Parameters:
    initial_raster_path (str): Path to the input raster file.

    Returns:
    GeoDataFrame: A GeoDataFrame with raster band data and square grid geometries.
    """
    try:
        # Open the raster file
        with rasterio.open(raster_path) as src:
            # Read the raster bands into a numpy array
            bands = src.read()
            band_count = src.count
            
            # Get the band names from the metadata
            band_names = src.descriptions if any(src.descriptions) else [f'band_{i+1}' for i in range(band_count)]
            
            # Create a DataFrame with each band as a column
            band_data = np.array([band.flatten() for band in bands]).T
            df = pd.DataFrame(band_data, columns=band_names)
            
            # Get the affine transformation of the raster
            transform = src.transform
            
            # Calculate the coordinates for each pixel
            rows, cols = np.indices(bands[0].shape)
            xs, ys = xy(transform, rows, cols)
            
            # Flatten the coordinates arrays
            xs = np.array(xs).flatten()
            ys = np.array(ys).flatten()
            
            # Filter out rows where all bands are NaN
            mask = ~np.all(np.isnan(band_data), axis=1)
            df = df[mask]
            xs = xs[mask]
            ys = ys[mask]
            
            # Create square polygons for each pixel
            pixel_size_x = transform.a
            pixel_size_y = -transform.e
            
            polygons = [box(x - pixel_size_x / 2, y - pixel_size_y / 2, x + pixel_size_x / 2, y + pixel_size_y / 2) for x, y in zip(xs, ys)]
            
            # Create a GeoDataFrame
            gdf = gpd.GeoDataFrame(df, geometry=polygons, crs=src.crs)
            
        return gdf
    
    except rasterio.errors.RasterioIOError as e:
        print(f"Error opening raster file: {e}")
        return None

def raster_clipping(shape_path, raster_path, file_name):
    """
    Clip a raster image using a shapefile and ensure CRS compatibility.
    """
    # Load the shapefile using GeoPandas to easily handle CRS
    gdf = gpd.read_file(shape_path)

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        # Check CRS compatibility, reproject if necessary
        if gdf.crs != raster_crs:
            print(f"Reprojecting shapefile from {gdf.crs} to {raster_crs}")
            gdf = gdf.to_crs(raster_crs)

        # Extract shapes from the GeoDataFrame for masking (convert to GeoJSON format)
        shapes = [mapping(geometry) for geometry in gdf.geometry]

        # Perform the masking operation
        out_image, out_transform = rio_mask(src, shapes=shapes, crop=True)  # <- Use renamed mask
        out_meta = src.meta

        # Update metadata for the output file
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

    # Define the path for the cropped raster
    cropped_raster_path = file_name

    # Write the cropped raster to file
    with rasterio.open(cropped_raster_path, "w", **out_meta) as dest:
        dest.write(out_image)

    print(f"Cropped raster saved to: {cropped_raster_path}")
    return cropped_raster_path



def inverted_clip_touching_gdf(gdf_to_clip, gdf_mask):
    """
    Clips all polygons from gdf_to_clip that do not intersect any polygon in gdf_mask, ensuring CRS consistency and reprojecting if necessary.
    
    Parameters:
    - gdf_to_clip (GeoDataFrame): The GeoDataFrame to be clipped.
    - gdf_mask (GeoDataFrame): The GeoDataFrame to use as the clipping mask.
    
    Returns:
    - GeoDataFrame: The inverted clipped GeoDataFrame containing only polygons that do not intersect the mask.
    """
    # Check CRS consistency
    if gdf_to_clip.crs != gdf_mask.crs:
        gdf_mask = gdf_mask.to_crs(gdf_to_clip.crs)
    
    # Combine all mask geometries into a single geometry
    combined_mask = gdf_mask.unary_union
    
    # Select polygons that do not intersect the mask
    not_intersecting_gdf = gdf_to_clip[~gdf_to_clip.geometry.intersects(combined_mask)]
    
    return not_intersecting_gdf

def generate_urban_mask(raster_path, threshold, save_path=None):
    """
    Generate an urban mask GeoDataFrame from a raster file based on a given threshold.

    Parameters
    ----------
    raster_path : str
        Path to the input raster file.
    threshold : int or float
        Threshold value to determine urban areas. Pixels with values above this threshold are considered urban (normal range is 0-30).
    save_path : str, optional
        Path to save the resulting GeoDataFrame as a file. If None, the file is not saved.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame containing the urban mask polygons.
    """
    # Step 1: Read the raster data
    with rasterio.open(raster_path) as mask_src:
        mask_data = mask_src.read(1)  # Read the first band
        mask_crs = mask_src.crs
        mask_transform = mask_src.transform

    # Step 2: Create a binary mask based on the threshold
    binary_mask = mask_data > threshold

    # Step 3: Convert the binary mask to polygons
    shapes_gen = shapes(binary_mask.astype(np.int16), transform=mask_transform)
    mask_polygons = [shape(geom) for geom, value in shapes_gen if value == 1]

    # Step 4: Convert polygons to GeoJSON-like dictionary
    mask_geom = [mapping(polygon) for polygon in mask_polygons]

    # Step 5: Transform mask_geom to GeoDataFrame
    urban_mask = gpd.GeoDataFrame(geometry=[shape(geom) for geom in mask_geom], crs=mask_crs)

    # Step 6: Optionally save the GeoDataFrame to a file
    if save_path:
        urban_mask.to_file(save_path)

    return urban_mask


def idw_interpolation(gdf, value_column, power=2):
    """
    Perform IDW interpolation to replace null values in the specified column of a GeoDataFrame.

    Parameters:
    gdf (GeoDataFrame): The input GeoDataFrame with geometry and value columns.
    value_column (str): The name of the column with the values to interpolate.
    power (float): The power parameter for IDW (default is 2).

    Returns:
    GeoDataFrame: The GeoDataFrame with null values replaced by IDW interpolated values.
    """
    # Separate the GeoDataFrame into known and unknown value parts
    known = gdf[gdf[value_column].notnull()]
    unknown = gdf[gdf[value_column].isnull()]
    
    # Use centroids for known and unknown geometries
    known_coords = np.array([(geom.centroid.x, geom.centroid.y) for geom in known.geometry])
    unknown_coords = np.array([(geom.centroid.x, geom.centroid.y) for geom in unknown.geometry])
    
    # Create a KDTree for known values
    tree = cKDTree(known_coords)
    
    # Define the IDW interpolation function
    def idw(x, y, z, xi, yi, power):
        distances, indices = tree.query([xi, yi], k=len(known_coords), distance_upper_bound=np.inf)
        weights = 1 / distances**power
        weights /= weights.sum()
        interpolated_value = np.dot(weights, z[indices])
        return interpolated_value

    # Apply IDW interpolation to each unknown value
    interpolated_values = []
    for geom in unknown.geometry:
        xi, yi = geom.centroid.x, geom.centroid.y
        z = known[value_column].values
        interpolated_value = idw(known_coords[:, 0], known_coords[:, 1], z, xi, yi, power)
        interpolated_values.append(interpolated_value)
    
    # Replace null values with interpolated values
    gdf.loc[gdf[value_column].isnull(), value_column] = interpolated_values
    
    return gdf

def plot_missing_values_vertical(df, filepath='.'):
    """
    Creates a heatmap showing missing values for each variable (column) of the DataFrame,
    with column names on the Y-axis.

    Args:
    df (DataFrame): The pandas DataFrame to analyze for missing values.
    """
    # Calculate the missing values in each column
    missing = df.isnull()

    # Create a heatmap visualization with rows and columns inverted
    plt.figure(figsize=(8, max(2, len(df.columns) * 0.25)))  # Adjust the figure size based on the number of columns
    sns.heatmap(missing.transpose(), cbar=False, cmap='viridis', yticklabels=True)

    # Add titles and labels in Spanish
    plt.title('Missing entries in each variable')
    plt.xlabel('Rows')
    plt.ylabel('Variables')

    if filepath != '.':
        plt.savefig(filepath)
    # Show the plot
    plt.show()

def plot_distribution_with_statistics(y,  filepath='.'):
    """
    Plots the distribution of a target variable with skewness and kurtosis values.

    Parameters:
    y (pd.Series or np.ndarray): The target variable data.

    Returns:
    None
    """
    # Calculate skewness and kurtosis
    skewness = skew(y)
    kurt = kurtosis(y)

    # Plot the distribution with skewness and kurtosis
    plt.figure(figsize=(10, 6))
    sns.histplot(y, bins=30, kde=True, color='skyblue')
    plt.title('Distribution of Target Variable')
    plt.xlabel('Value')
    plt.ylabel('Frequency')

    # Add skewness and kurtosis text to the plot
    plt.text(x=0.95, y=0.95, s=f'Skewness: {skewness:.2f}', horizontalalignment='right', verticalalignment='top', transform=plt.gca().transAxes, fontsize=12)
    plt.text(x=0.95, y=0.90, s=f'Kurtosis: {kurt:.2f}', horizontalalignment='right', verticalalignment='top', transform=plt.gca().transAxes, fontsize=12)

    if filepath != '.':
        plt.savefig(filepath)
    
    # Show the plot
    
    plt.show()

# Function to plot histograms in a grid with more bins
def plot_histograms(df, bins=50):
    num_cols = len(df.columns)
    num_rows = (num_cols + 1) // 2  # To arrange histograms in a grid (2 columns)
    
    fig, axes = plt.subplots(num_rows, 2, figsize=(10, num_rows * 3))
    axes = axes.flatten()  # Flatten the axes array to access each subplot easily
    
    for i, col in enumerate(df.columns):
        axes[i].hist(df[col], bins=bins, edgecolor='black')
        axes[i].set_title(col)
    
    # Remove any empty subplots
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])
    
    plt.tight_layout()
    plt.show()

def log_transform(df):
    return pd.DataFrame(np.log1p(df.iloc[:, 0]), columns=df.columns)

def sqrt_transform(df):
    return pd.DataFrame(np.sqrt(df.iloc[:, 0]), columns=df.columns)

def square_transform(df):
    return pd.DataFrame(np.square(df.iloc[:, 0]), columns=df.columns)

def boxcox_transform(df):
    transformed_y, lmbda = boxcox(df.iloc[:, 0])
    return pd.DataFrame(transformed_y, columns=df.columns), lmbda

def select_transformation(df, zero_threshold=0.1, shift_value=0.01):
    """
    Selects the best transformation for the target variable based on its distribution characteristics,
    including skewness, kurtosis, and the presence of excessive zeros.

    Parameters:
    df (pd.DataFrame): The target variable data with a single column.
    zero_threshold (float): Proportion of zeros above which a shift will be applied.
    shift_value (float): The constant added to each value if there are too many zeros.

    Returns:
    tuple: (transformed_df, transformation_name, lmbda)
           - transformed_df (pd.DataFrame): The transformed target variable with the original column name.
           - transformation_name (str): The name of the applied transformation.
           - lmbda (float or None): The lambda value used for Box-Cox transformation.
                                    None if the transformation does not require lambda.
    """
    y = df.iloc[:, 0]
    skewness = skew(y)
    kurt = kurtosis(y)
    print(f"Skewness: {skewness}, Kurtosis: {kurt}")
    
    # Check proportion of zeros
    zero_proportion = (y == 0).mean()
    if zero_proportion > zero_threshold:
        print(f"High proportion of zeros detected ({zero_proportion:.2%}). Applying a shift of {shift_value}.")
        y = y + shift_value  # Shift values to reduce zero inflation
    
    # Recreate the DataFrame after potential shift
    df = pd.DataFrame(y, columns=df.columns)

    if np.any(y <= 0):
        # If there are non-positive values, avoid log and Box-Cox transformations
        if skewness > 1:
            print("Applying square root transformation due to high positive skewness and non-positive values.")
            return sqrt_transform(df), 'sqrt', None
        elif skewness > 0.5:
            print("Applying square root transformation due to moderate positive skewness and non-positive values.")
            return sqrt_transform(df), 'sqrt', None
        elif skewness < -1:
            print("Applying square transformation due to high negative skewness and non-positive values.")
            return square_transform(df), 'square', None
        elif -0.5 < skewness < 0.5:
            print("No transformation applied due to low skewness and non-positive values.")
            return df, 'none', None  # No transformation
        else:
            print("Applying square root transformation due to other skewness values and non-positive values.")
            return sqrt_transform(df), 'sqrt', None
    else:
        # If all values are positive, consider all transformations
        if skewness > 1:
            print("Applying log transformation due to high positive skewness.")
            return log_transform(df), 'log', None
        elif skewness > 0.5:
            print("Applying square root transformation due to moderate positive skewness.")
            return sqrt_transform(df), 'sqrt', None
        elif skewness < -1:
            print("Applying square transformation due to high negative skewness.")
            return square_transform(df), 'square', None
        elif -0.5 < skewness < 0.5:
            print("No transformation applied due to low skewness.")
            return df, 'none', None  # No transformation
        else:
            try:
                print("Applying Box-Cox transformation due to other skewness values.")
                transformed_df, lmbda = boxcox_transform(df)
                return transformed_df, 'box-cox', lmbda
            except ValueError:
                print("Box-Cox transformation failed; no transformation applied.")
                return df, 'none', None

def revert_transformation(y_transformed, transformation_name, original_mean=None, original_std=None, lmbda=None):
    """
    Reverts the transformation applied to the target variable based on the transformation name.

    Parameters:
    y_transformed (np.ndarray): The transformed target variable data.
    transformation_name (str): The name of the applied transformation.
    original_mean (float, optional): The mean of the original target variable, required if standardized.
    original_std (float, optional): The standard deviation of the original target variable, required if standardized.
    lmbda (float, optional): The lambda value used for the Box-Cox or Yeo-Johnson transformation, if applicable.

    Returns:
    np.ndarray: The reverted target variable, in its original form.

    Raises:
    ValueError: If the transformation name is not recognized.
    """

    if transformation_name == 'log':
        return expm1(y_transformed)
    elif transformation_name == 'sqrt':
        return square(y_transformed)
    elif transformation_name == 'square':
        return sqrt(y_transformed)
    elif transformation_name == 'box-cox':
        if lmbda is None:
            raise ValueError("Lambda value is required to revert Box-Cox transformation.")
        return inv_boxcox(y_transformed, lmbda)
    elif transformation_name == 'yeo-johnson':
        if lmbda is None:
            raise ValueError("Lambda value is required to revert Yeo-Johnson transformation.")
        return yeojohnson_inverse(y_transformed, lmbda)
    elif transformation_name == 'none':
        return y_transformed
    else:
        raise ValueError(f"Unrecognized transformation name: {transformation_name}")

def revert_standardization(y_standardized, original_mean, original_std):
    """
    Reverts the standardization process by applying the inverse of standardization.

    Parameters:
    y_standardized (np.ndarray): The standardized target variable.
    original_mean (float): The mean of the original target variable before standardization.
    original_std (float): The standard deviation of the original target variable before standardization.

    Returns:
    np.ndarray: The original target variable before standardization.
    """
    return y_standardized * original_std + original_mean

def yeojohnson_inverse(y_transformed, lmbda):
    """
    Reverts the Yeo-Johnson transformation given the transformed data and lambda parameter.

    Parameters:
    y_transformed (np.ndarray): The Yeo-Johnson transformed data.
    lmbda (float): The lambda value used in the Yeo-Johnson transformation.

    Returns:
    np.ndarray: The original data before Yeo-Johnson transformation.
    """
    if lmbda == 0:
        return expm1(y_transformed)
    elif lmbda > 0:
        return np.exp(np.log1p(y_transformed * lmbda) / lmbda) - 1
    else:
        return -np.exp(np.log1p(-y_transformed * lmbda) / -lmbda) + 1


def filter_columns_by_year(gdf: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Filters the columns of a given DataFrame to retain only those that are associated with a specified year,
    one year before, and one year after, as well as any columns that do not contain a year in their name.

    Parameters:
    ----------
    gdf : pd.DataFrame
        The input DataFrame containing columns with and without year-based names.

    year : int
        The reference year for filtering columns. Columns with names containing this year,
        one year before, and one year after will be retained.

    Returns:
    -------
    pd.DataFrame
        A DataFrame containing only the filtered columns that meet the criteria of matching
        the specified year, one year before, and one year after, or having no year in their name.

    Example:
    -------
    Given a DataFrame `gdf` with columns ['tcc1990', 'tcc1991', 'tcc1992', 'population', 'area']:
    - Calling `filter_columns_by_year(gdf, 1991)` will return a DataFrame with columns
      ['tcc1990', 'tcc1991', 'tcc1992', 'population', 'area'].

    Notes:
    -----
    - The function assumes that columns containing years follow the format 'XXXX' where 'XXXX'
      is a four-digit number representing the year.
    - Columns that do not contain any year will be retained in the output DataFrame.
    """
    
    # Convert the year to string for easy matching
    year_str = str(year)
    year_before_str = str(year - 1)
    year_after_str = str(year + 1)
    
    # Function to check if a column name matches the year, one year before, or one year after
    def match_year(column_name):
        # Extract year from column name if it exists
        year_match = re.search(r'\d{4}', column_name)
        if year_match:
            col_year = year_match.group(0)
            return col_year in [year_str, year_before_str, year_after_str]
        else:
            # If no year found in column name, keep it
            return True
    
    # Filter columns based on the matching criteria
    filtered_columns = [col for col in gdf.columns if match_year(col)]
    
    # Return the filtered DataFrame
    return gdf[filtered_columns]

def raster_freq_table(raster_path):

    '''Returns a frequency table for the rasters values'''
    
    # Load the new raster file
    dataset = gdal.Open(raster_path)
    
    # Read the first band
    band = dataset.GetRasterBand(1)
    array = band.ReadAsArray()
    
    # Flatten the array to make frequency counting feasible
    flat_array = array.flatten()
    
    # Replace nodata values with nan to exclude them from the frequency count
    nodata_value = band.GetNoDataValue()
    if nodata_value is not None:
        flat_array = np.where(flat_array == nodata_value, np.nan, flat_array)
    
    # Remove nan values for frequency counting
    flat_array_nonan = flat_array[~np.isnan(flat_array)]
    
    # Generate frequency table
    unique, counts = np.unique(flat_array_nonan, return_counts=True)
    frequency_table = pd.DataFrame({"Value": unique, "Frequency": counts})
    
    return frequency_table

def df_to_pdf(df, file_path, title='.', show=False):
    """
    Converts a DataFrame to a PDF with an optional title.

    Parameters:
    df (pandas.DataFrame): The DataFrame to convert to PDF.
    file_path (str): The path to save the PDF.
    title (str): The title of the PDF (default is '.').
    show (bool): Whether to display the PDF after saving (default is False).
    """
    fig, ax = plt.subplots(figsize=(8, 4))  # Set the size of the figure
    ax.axis('tight')
    ax.axis('off')

    # Set the title before saving
    if title != '.':
        ax.set_title(title, fontsize=14, pad=20)

    # Create the table from the DataFrame
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')

    # Save the plot as a PDF
    plt.savefig(file_path, bbox_inches='tight')

    # Optionally show the plot
    if show:
        plt.show()

    # Close the plot to free up resources
    plt.close()


def estimate_reasonable_beta(coordinates, values, plot_variogram=False):
    """
    Estimate a reasonable beta for the HalfCauchy prior based on the variogram of the target variable.
    
    Parameters:
    - coordinates: List of (x, y) tuples representing the spatial coordinates.
    - values: List or array of target variable values corresponding to the coordinates.
    - plot_variogram: Whether to plot the variogram for visual inspection (default is False).
    
    Returns:
    - beta: A reasonable beta for the HalfCauchy prior for length scale (ls).
    """
    # Step 1: Calculate pairwise distances
    distances = pdist(coordinates, metric='euclidean')
    
    # Get summary statistics for distances
    min_distance = np.min(distances)
    max_distance = np.max(distances)
    mean_distance = np.mean(distances)
    
    print(f"Min distance: {min_distance}")
    print(f"Max distance: {max_distance}")
    print(f"Mean distance: {mean_distance}")
    
    # Step 2: Create and analyze variogram
    variogram = Variogram(coordinates, values, normalize=False)
    
    # Plot the variogram if required
    if plot_variogram:
        variogram.plot()
        plt.title("Variogram of Target Variable")
        plt.xlabel("Distance")
        plt.ylabel("Semi-variance")
        plt.show()

    # Step 3: Determine the range where the variogram levels off (effective range)
    range_estimate = variogram.parameters[0]  # The 'range' from the variogram model
    
    print(f"Estimated range from variogram: {range_estimate}")
    
    # Step 4: Determine a reasonable beta for HalfCauchy prior based on the range
    # Use thresholds based on the proportion of the maximum distance
    if range_estimate < 0.1 * max_distance:
        beta = 0.5  # Short-range correlation
        print("Short-range correlation detected. Setting beta to 0.5.")
    elif range_estimate < 0.5 * max_distance:
        beta = 1.0  # Moderate correlation
        print("Moderate-range correlation detected. Setting beta to 1.0.")
    else:
        beta = 2.0  # Long-range correlation
        print("Long-range correlation detected. Setting beta to 2.0.")
    
    return beta


def auto_transform(df):
    """
    Automatically identify and apply the necessary transformations to the DataFrame.

    Parameters:
    df (pd.DataFrame): The input DataFrame with covariates.

    Returns:
    pd.DataFrame: A new DataFrame with transformations applied.
    """

    def identify_transformation(df):
        """
        Identify the type of transformation needed for each column.

        Parameters:
        df (pd.DataFrame): The input DataFrame.

        Returns:
        log_columns, binary_columns, other_columns (lists): Columns to log transform, binary columns, and columns needing Yeo-Johnson transform.
        """
        log_columns = []
        binary_columns = []
        other_columns = []
        
        # Loop through each column and identify the needed transformation
        for col in df.columns:
            unique_values = df[col].nunique()
            if unique_values == 2:  # Binary column (e.g., 0 and 1)
                binary_columns.append(col)
            elif (df[col] > 0).all():  # Log transformable (strictly positive values)
                log_columns.append(col)
            else:  # Apply Yeo-Johnson to handle negative or skewed values
                other_columns.append(col)
        
        return log_columns, binary_columns, other_columns

    def build_preprocessor(df):
        """
        Build a ColumnTransformer based on the identified transformations for each column.

        Parameters:
        df (pd.DataFrame): The input DataFrame.

        Returns:
        ColumnTransformer: A preprocessor object that applies transformations.
        """
        log_columns, binary_columns, other_columns = identify_transformation(df)
        
        # Define the necessary transformers
        log_transform = FunctionTransformer(np.log1p, validate=True)  # Log transformation
        binary_transform = 'passthrough'  # No transformation for binary columns
        yeo_johnson_transform = PowerTransformer(method='yeo-johnson')  # Yeo-Johnson transformation

        # Build the preprocessor
        preprocessor = ColumnTransformer(
            transformers=[
                ('log', log_transform, log_columns),
                ('binary', binary_transform, binary_columns),
                ('yeo_johnson', yeo_johnson_transform, other_columns)
            ]
        )
        
        return preprocessor

    # Build the preprocessor for the input DataFrame
    preprocessor = build_preprocessor(df)

    # Fit and transform the DataFrame
    transformed_data = preprocessor.fit_transform(df)

    # Convert the transformed data back into a DataFrame
    transformed_df = pd.DataFrame(transformed_data, columns=df.columns)

    return transformed_df


def sort_key(filename):
    """
    Extracts leading numerical parts from the filename for sorting numerically,
    and then alphabetically for any non-numerical parts.
    """
    # Use a regular expression to split the filename into numeric and non-numeric parts
    parts = re.split(r'(\d+)', filename)
    # Convert numeric parts to integers for proper numeric sorting
    return [int(part) if part.isdigit() else part.lower() for part in parts]

def create_pdf_report(destination, source, report_name):
    """
    Manages PDF files by performing the following actions:
    
    1. Creates a directory at the specified destination path if it doesn't exist.
    2. Copies all .pdf files from the source directory to the destination directory.
    3. Deletes all files in the source directory.
    4. Merges all .pdf files from the destination directory into a single PDF file named 'Report.pdf',
       ensuring the files are sorted numerically first and alphabetically second.

    Parameters:
    destination (str): The path where the new directory is created and PDFs are copied to.
    source (str): The path from where PDFs are copied and all files are erased.
    report_name (str): name of the final PDF file.

    Example:
    manage_pdfs('/path/to/destination', '/path/to/source')
    """
    # Step 1: Create a directory at destination
    if not os.path.exists(destination):
        os.makedirs(destination)
    
    # Step 2: Copy all .pdf files from source to destination
    for filename in os.listdir(source):
        if filename.endswith('.pdf'):
            shutil.copy(os.path.join(source, filename), os.path.join(destination, filename))
    
    # Step 3: Erase all files from source
    for filename in os.listdir(source):
        file_path = os.path.join(source, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    
    # Step 4: Combine all files from destination into a single PDF
    merger = PdfMerger()

    # Get a list of .pdf files and sort them numerically then alphabetically
    pdf_files = sorted([f for f in os.listdir(destination) if f.endswith('.pdf')], key=sort_key)

    for filename in pdf_files:
        merger.append(os.path.join(destination, filename))
    
    output_path = os.path.join(destination, report_name)
    merger.write(output_path)
    merger.close()

import rasterio
from rasterio.mask import mask
import geopandas as gpd
import os

def clip_raster_exclude_shape(raster_path, shapefile_path, output_path):
    """
    Clips a raster file using a shapefile and keeps the pixels on the raster that do not overlap with the shape.

    Parameters:
        raster_path (str): Path to the input raster file.
        shapefile_path (str): Path to the shapefile used for clipping.
        output_path (str): Path to save the output clipped raster file.

    Returns:
        None

    Raises:
        ValueError: If the CRS of the raster and shapefile do not match and cannot be reprojected.
    """
    # Read the shapefile
    shapefile = gpd.read_file(shapefile_path)

    # Ensure the shapefile and raster have the same CRS
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs

        if shapefile.crs != raster_crs:
            try:
                shapefile = shapefile.to_crs(raster_crs)
            except Exception as e:
                raise ValueError(f"Failed to reproject shapefile to raster CRS: {e}")

        # Convert shapefile geometries to a list of GeoJSON-like objects
        shapes = [geometry for geometry in shapefile.geometry]

        try:
            # Create an inverted mask
            out_image, out_transform = mask(src, shapes=shapes, invert=True, crop=False)

            # Update metadata
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": src.transform,
            })
        except TypeError as te:
            raise TypeError(f"Error during masking operation: {te}")

    # Save the masked raster to a new file
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(out_image)

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import contextily as ctx
import rasterio
from rasterio.mask import mask
import geopandas as gpd
import os

def plot_treatment_control_grids(gdf, treatment_column, crs, title='.'):
    """
    Plots a map of treatment and control grids with a basemap and legend.

    Parameters:
        gdf (GeoDataFrame): GeoDataFrame containing the data to plot.
        treatment_column (str): Name of the column indicating treatment values.
        crs: Coordinate reference system of the GeoDataFrame.
    """
    # Create a color mapping based on the Treatment values
    color_map = {
        1: 'blue',    # Treatment areas
        0: 'red',     # Control areas
        3: 'white'    # Neither control nor treatment
    }

    # Map the Treatment values to colors
    gdf['color'] = gdf[treatment_column].map(color_map)

    # Create a plot
    fig, ax = plt.subplots(figsize=(10, 10))

    # Plot the grid, using the color column
    gdf.plot(ax=ax, color=gdf['color'], edgecolor='black', alpha=0.6)

    # Add a black-and-white basemap (Stamen Toner Lite)
    ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, alpha=0.9, crs=crs)

    # Add title and axis labels
    if title=='.':
        ax.set_title('Treatment and Control Grids')
    if title!='.':
        ax.set_title(title)
    
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')

    # Add a legend manually
    treated_patch = mpatches.Patch(color='blue', label='Treated Grids')
    control_patch = mpatches.Patch(color='red', label='Control Grids')
    ax.legend(handles=[treated_patch, control_patch], loc='upper right', title='Legend')

    # Show the plot
    plt.show()


def plot_histogram_with_mean(df, column, bins=10, title='.', color='blue', line_color='red', line_style='dotted'):
    """
    Plots a histogram of a specified column in a DataFrame and adds a vertical line at the mean.
    
    Parameters:
        df (pd.DataFrame): The DataFrame containing the data.
        column (str): The column name to plot the histogram for.
        bins (int): Number of bins for the histogram. Default is 10.
        color (str): Color of the histogram bars. Default is 'blue'.
        line_color (str): Color of the mean line. Default is 'red'.
        line_style (str): Line style for the mean line. Default is 'dotted'.
    """
    # Compute the mean
    mean_value = df[column].mean()
    
    # Plot the histogram
    plt.hist(df[column], bins=bins, alpha=0.7, edgecolor='black', color=color)
    
    # Add a vertical line at the mean
    plt.axvline(mean_value, color=line_color, linestyle=line_style, linewidth=2, label=f'Mean: {mean_value:.2f}')
    
    # Add labels and legend
    plt.xlabel(column.capitalize())
    plt.ylabel('Frequency')
    
    if title=='.': 
        title = f'histogram of {column}'
    
    plt.title(title)
    plt.legend()
    
    # Show the plot
    plt.show()

def clip_raster_with_shapefile(raster_path, shapefile_path, output_path):
    """
    Clips a raster file using a shapefile and saves a new masked raster.

    Parameters:
        raster_path (str): Path to the input raster file.
        shapefile_path (str): Path to the shapefile used for clipping.
        output_path (str): Path to save the output clipped raster file.

    Returns:
        None
    """
    # Read the shapefile
    shapefile = gpd.read_file(shapefile_path)

    # Ensure the shapefile and raster have the same CRS
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs

    if shapefile.crs != raster_crs:
        shapefile = shapefile.to_crs(raster_crs)

    # Convert shapefile geometries to a list of GeoJSON-like objects
    shapes = [feature["geometry"] for feature in shapefile.iterfeatures()]

    # Open the raster file
    with rasterio.open(raster_path) as src:
        # Mask the raster with the shapes
        out_image, out_transform = mask(src, shapes, crop=True)

        # Update metadata
        out_meta = src.meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
        })

    # Save the clipped raster to a new file
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(out_image)


# Example usage
# clip_raster_with_shapefile(
#     "input_raster.tif", "clip_shapefile.shp", "output_clipped_raster.tif"
# )

import rasterio
from rasterio.mask import mask
import geopandas as gpd
import os

def clip_raster_exclude_shape(raster_path, shapefile_path, output_path):
    """
    Clips a raster file using a shapefile and keeps the pixels on the raster that do not overlap with the shape.

    Parameters:
        raster_path (str): Path to the input raster file.
        shapefile_path (str): Path to the shapefile used for clipping.
        output_path (str): Path to save the output clipped raster file.

    Returns:
        None

    Raises:
        ValueError: If the CRS of the raster and shapefile do not match and cannot be reprojected.
    """
    # Read the shapefile
    shapefile = gpd.read_file(shapefile_path)

    # Ensure the shapefile and raster have the same CRS
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs

        if shapefile.crs != raster_crs:
            try:
                shapefile = shapefile.to_crs(raster_crs)
            except Exception as e:
                raise ValueError(f"Failed to reproject shapefile to raster CRS: {e}")

        # Convert shapefile geometries to a list of GeoJSON-like objects
        shapes = [geometry for geometry in shapefile.geometry]

        try:
            # Create an inverted mask
            out_image, out_transform = mask(src, shapes=shapes, invert=True, crop=False)

            # Update metadata
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": src.transform,
            })
        except TypeError as te:
            raise TypeError(f"Error during masking operation: {te}")

    # Save the masked raster to a new file
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(out_image)


def calculate_average_raster_value(raster_path, shapefile_path):
    """
    Calculates the average value of all pixels in a raster file that intersect with a shapefile.

    Parameters:
        raster_path (str): Path to the input raster file.
        shapefile_path (str): Path to the shapefile.

    Returns:
        float: The average value of the intersecting pixels, or None if no pixels intersect.

    Raises:
        ValueError: If the CRS of the raster and shapefile do not match and cannot be reprojected.
    """
    # Read the shapefile
    shapefile = gpd.read_file(shapefile_path)

    # Ensure the shapefile and raster have the same CRS
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs

        if shapefile.crs != raster_crs:
            try:
                shapefile = shapefile.to_crs(raster_crs)
            except Exception as e:
                raise ValueError(f"Failed to reproject shapefile to raster CRS: {e}")

        # Convert shapefile geometries to a list of GeoJSON-like objects
        shapes = [geometry for geometry in shapefile.geometry]

        try:
            # Mask the raster with the shapes
            out_image, _ = mask(src, shapes=shapes, crop=True)

            # Extract the masked data
            masked_data = out_image[0]  # Assuming single-band raster

            # Replace nodata values with NaN for proper averaging
            nodata = src.nodata
            if nodata is not None:
                masked_data = np.where(masked_data == nodata, np.nan, masked_data)

            # Calculate the average, ignoring NaN values
            if np.isnan(masked_data).all():
                return None

            average_value = np.nanmean(masked_data)

            return average_value

        except Exception as e:
            raise RuntimeError(f"Error during masking or averaging: {e}")



