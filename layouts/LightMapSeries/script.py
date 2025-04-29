import arcpy
import os
import time

# -------------------- Settings: Configure Before Running --------------------

workspace = "ADD PATH TO WORKSPACE C:/..."
arcpy.env.workspace = workspace
arcpy.env.overwriteOutput = True
output_gdb = os.path.join(workspace, "Outputs.gdb")

# Input datasets
counties_fc = os.path.join(workspace, "US_Counties.shp")
raster_input = os.path.join(workspace, "LightPollution.tif")
cities_fc = os.path.join(workspace, "US_Major_Cities.shp") 

# Output layers
megaregion_fc = os.path.join(output_gdb, "Megaregion_Counties")
selected_counties = os.path.join(output_gdb, "HighDensityCounties")
clipped_raster = os.path.join(output_gdb, "LightPollution_Clipped")
major_cities_fc = os.path.join(output_gdb, "MajorCities_Over500K")  # New output
clipped_cities_fc = os.path.join(output_gdb, "MajorCities_ClippedToMegaregion")

# Megaregion selection (state definitions for each)
megaregions = {
    "Northeast": [
        'New York', 'New Jersey', 'Massachusetts', 'Pennsylvania',
        'Connecticut', 'Rhode Island', 'Maryland', 'Delaware',
        'District of Columbia'
    ],
    "Great Lakes": [
        'Illinois', 'Indiana', 'Michigan', 'Minnesota', 'Ohio', 'Wisconsin'
    ],
    "Piedmont Atlantic": [
        'Georgia', 'North Carolina', 'South Carolina', 'Alabama', 'Tennessee'
    ],
    "Texas Triangle": [
        'Texas', 'Louisiana'
    ],
    "Southern California": [
        'California', 'Arizona'
    ]
}

# Choose the megaregion
megaregion_name = "Northeast"  
megaregion_states = megaregions[megaregion_name]


density_threshold = 500  # people per square mile 
city_pop_threshold = 400000  # people

# Use provided raster symbology
raster_symbology_layer = os.path.join(workspace, "LightPollution_Symbology.lyrx")

 
# -------------------- Function to Reproject Layers --------------------

def reproject_layers(megaregion_name, counties_fc, cities_fc, raster_input):
    # Define the correct UTM projection for each megaregion
    projections = {
        "Northeast": "EPSG:26918",  # UTM Zone 18N
        "Great Lakes": "EPSG:26916",  # UTM Zone 16N
        "Piedmont Atlantic": "EPSG:26917",  # UTM Zone 17N
        "Texas Triangle": "EPSG:26914",  # UTM Zone 14N
        "Southern California": "EPSG:26911",  # UTM Zone 11N
    }

    # Get the UTM projection for the selected megaregion
    utm_projection = projections.get(megaregion_name)

    if not utm_projection:
        raise ValueError(f"Projection for megaregion '{megaregion_name}' not found.")

    # Reproject counties, cities, and raster layers
    counties_reprojected = os.path.join(output_gdb, "Counties_Reprojected")
    cities_reprojected = os.path.join(output_gdb, "Cities_Reprojected")
    raster_reprojected = os.path.join(output_gdb, "LightPollution_Reprojected.tif")

    # Reproject the counties feature class
    arcpy.Project_management(counties_fc, counties_reprojected, utm_projection)
    print(f"Counties reprojected to {utm_projection}: {counties_reprojected}")

    # Reproject the cities feature class
    arcpy.Project_management(cities_fc, cities_reprojected, utm_projection)
    print(f"Cities reprojected to {utm_projection}: {cities_reprojected}")

    # Reproject the raster
    arcpy.ProjectRaster_management(raster_input, raster_reprojected, utm_projection)
    print(f"Raster reprojected to {utm_projection}: {raster_reprojected}")

    return counties_reprojected, cities_reprojected, raster_reprojected

# -------------------- Execution --------------------

start_time = time.time()

# Step 1: Reproject the layers to the appropriate UTM projection for the megaregion
counties_fc_reprojected, cities_fc_reprojected, raster_input_reprojected = reproject_layers(
    megaregion_name, counties_fc, cities_fc, raster_input
)

# Step 2: Select counties in the megaregion
state_names = ', '.join([f"'{state}'" for state in megaregion_states])
region_query = f'"STATE_NAME" IN ({state_names})'
arcpy.Select_analysis(counties_fc_reprojected, megaregion_fc, region_query)
print(f"Selected counties in megaregion: {megaregion_fc}")

# Step 3: Add population density and filter high-density areas
fields = [f.name for f in arcpy.ListFields(megaregion_fc)]
if "Population_Density" not in fields:
    arcpy.AddField_management(megaregion_fc, "Population_Density", "DOUBLE")
    arcpy.CalculateField_management(
        megaregion_fc,
        "Population_Density",
        "!Population! / !AREA_SQMI!",
        "PYTHON3"
    )
    print("Population density field calculated.")

density_query = f'"Population_Density" > {density_threshold}'
arcpy.Select_analysis(megaregion_fc, selected_counties, density_query)
print(f"High-density counties selected: {selected_counties}")

# Step 4: Clip light pollution raster to selected counties
arcpy.Clip_management(
    in_raster=raster_input_reprojected,
    rectangle="",
    out_raster=clipped_raster,
    in_template_dataset=selected_counties,
    nodata_value="0",
    clipping_geometry="ClippingGeometry",
    maintain_clipping_extent="NO_MAINTAIN_EXTENT"
)
print(f"Raster clipped to high-density counties: {clipped_raster}")

# Step 4.5: Apply symbology from original light pollution layer
arcpy.ApplySymbologyFromLayer_management(clipped_raster, raster_symbology_layer)
print(f"Symbology applied to clipped raster using {raster_symbology_layer}")


# Step 5: Select major cities with population > selected threshold
city_pop_query = f'"Population" > {city_pop_threshold}'
arcpy.Select_analysis(cities_fc_reprojected, major_cities_fc, city_pop_query)
print(f"Major cities over {city_pop_threshold} extracted: {major_cities_fc}")

# Step 6: Clip the selected major cities to only those within the megaregion counties
arcpy.Clip_analysis(
    in_features=major_cities_fc,
    clip_features=selected_counties,
    out_feature_class=clipped_cities_fc
)
print(f"Major cities clipped to megaregion counties: {clipped_cities_fc}")

# Report execution time
end_time = time.time()
print(f"\n Process completed in {round(end_time - start_time, 2)} seconds.")



