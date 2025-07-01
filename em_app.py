import dash_leaflet as dl
from dash import Dash, html, Output, Input, State, dcc, dash_table, no_update, callback_context
import dash_leaflet.express as dlx
import pandas as pd
from dash_extensions.javascript import Namespace, assign
from dash import Dash, html
import numpy as np
import geopandas as gp
from shapely.geometry import Point,Polygon
import plotly.express as px
from flask_caching import Cache
import os
import random

def read_og_df(directory):
    if os.path.isfile(directory):
        df = pd.read_csv(directory, dtype={'PostalCode': str})
        df = df[~df['TerritoryName'].isna()]
        new_row = pd.DataFrame([dict(zip(df.columns,[0 if x!= 'TerritoryName' else 'New' for x in df.columns]))])
        df = pd.concat([df,new_row], ignore_index = True)
        df = df.dropna()
        # this returns the long format original df, which is also referred to as og df
        return df

# can use after running setup_data(), aka after cat_terr_map is initialized
def update_zip(df):
    """Updates table used in zipcode hoverover info whenever territories are selected/modified
    
    Args:
        df: long format df

    Returns:
        df with totals at the zipcode level and category for coloring 
    """
    zipcodedf = zipcodetable(df)
    zipcodedf['category'] = zipcodedf['TerritoryName'].apply(lambda x: cat_terr_map[x])
    return zipcodedf

# to retrieve coordinates of shapes (polygons) drawn on map
def find_geo(d):
    res = []
    try:
        for v in d['features']:
            if v['geometry']['type'] == 'Polygon':
                res.append(v['geometry']['coordinates'])
        return res
    except:
        return None

def dict_to_gpd(ex):
    extracted_coords = [i['geometry']['coordinates'] for i in ex['features']]
    extracted_features =[i['properties'] for i in ex['features']]
    for i,k in enumerate(extracted_features):
        k['coords'] = Point(extracted_coords[i])
    return gp.GeoDataFrame(extracted_features, geometry='coords')

def dict_to_pd(ex):
    extracted_coords = [i['geometry']['coordinates'] for i in ex['features']]
    extracted_features = [i['properties'] for i in ex['features']]
    temp_df = pd.DataFrame(extracted_features)
    lats = []
    longs = []
    for i,k in enumerate(extracted_features):
        longs.append(extracted_coords[i][0])
        lats.append(extracted_coords[i][1])
    temp_df['Latitude'] = lats
    temp_df['Longitude'] = longs
    return temp_df

def totalstable(level, df):
    """Converts raw df to displayed bottom table, which calculates sums at the specified level

    Args:
        level: one of either 'PostalCode' or 'TerritoryName', i.e. column name to group by
        df: long format df
    
    Returns:
        df of bottom table of the app, which has total oppty value, total oppty count, and 
        total value by oppty type at the specified level
    """
    # temp1: calculate Total Opportunity Value
    ## calculate total value for each opportunity type
    temp1 = df.groupby([level, 'OpptyType'])['TotalAssets'].sum().unstack().fillna(0).reset_index()
    ## calculate total value across all types
    temp1['TotalOpptyValue'] = temp1.sum(axis=1, numeric_only=True)
    ## artifically create columns if any opportunity types DNE
    keepcols = ['Type A', 'Type B', 'Type C']
    temp1 = temp1.reindex(temp1.columns.union(keepcols, sort=False), axis=1, fill_value=0)
    temp1 = temp1[[level, 'TotalOpptyValue', 'Type A', 'Type B', 'Type C']]

    # temp3: calculate total count (rows) of opportunities for each level
    temp3 = df.groupby([level])['ProducerName'].count().reset_index().rename(columns={'ProducerName': 'TotalOpptyCount'})
    ## subtract 1 from TotalOpptyCount for 'New' territory, as it will always have a row of 0s
    if level == 'TerritoryName':
        temp3.loc[temp3[level]=='New', 'TotalOpptyCount'] -= 1
    else:  # for zipcode 0
        temp3.loc[temp3[level]==0, 'TotalOpptyCount'] -= 1
    
    return temp1.merge(temp3)

def zipcodetable(df):
    """Calculates totals at the zipcode level, used in hoverover information

    Args:
        df: long format df
    
    Returns:
        df with total opportunity count, opportunity value, and number of producers at the zipcode level
    """
    # calculate number of producers per zipcode
    temp1 = pd.DataFrame(df.groupby(['TerritoryName', 'PostalCode', 'Latitude', 'Longitude'])['ProducerName'].nunique()).reset_index()
    temp1 = temp1.rename(columns={'ProducerName': 'Producers'})
    # find row indexes of 'New' territory
    newterr = temp1[temp1['TerritoryName'] == 'New'].index.values.tolist()
    # find row of 0s and change number of Producers to 0
    for idx in newterr:
        if all(temp1.loc[[idx]].drop(['TerritoryName', 'Producers'], axis=1).squeeze(axis=0) == 0):
            temp1.loc[idx, 'Producers'] = 0

    # calculate totals at the zipcode level
    temp2 = totalstable('PostalCode', df)
    return temp1.merge(temp2)

# the long hoverover caption
def hoverdict(zipcodedf):
    """Creates the tooltip hoverover label for each zipcode

    Args:
        zipcodedf: df output of zipcodetable, which has information at the zipcode level
    
    Returns:
        dict where each item (zipcode) has a tooltip key that corresponds with the displayed hover text
    """
    dicts = zipcodedf.to_dict('records')
    for item in dicts:
        item["tooltip"] = f"<b>ZIP: {item['PostalCode']}</b>,</br>" + \
            f"Producer Count: {item['Producers']},</br>" + \
            f"Total Opportunity Value: {item['TotalOpptyValue']},</br>" + \
            f"Total Opportunity Count: {item['TotalOpptyCount']},</br>" + \
            f"Type A: {item['Type A']},</br>" + \
            f"Type B: {item['Type B']},</br>" + \
            f"Type C: {item['Type C']},</br>" + \
            f"<b>Territory Name: ({item['TerritoryName']})</b>" 
    return dicts


#################### SET UP STARTING DATA ######################################
def setup_data(directory):
    df = read_og_df(directory)
    # initialize zipcode df
    zip_df = zipcodetable(df)
    category, uniques = pd.factorize(zip_df['TerritoryName'])
    cat_terr_map = dict(zip(uniques,list(range(len(uniques)))))
    zip_df['category'] = category
    zip_df = zip_df.dropna()
    dicts = hoverdict(zip_df)

    geojson = dlx.dicts_to_geojson(dicts, lon="Longitude", lat = "Latitude")  # convert to geojson
    geobuf = dlx.geojson_to_geobuf(geojson)  # convert to geobuf
    return df, zip_df, category, uniques, cat_terr_map, geojson, geobuf

directory = "assets/sample_data.csv"
df, zip_df, category, uniques, cat_terr_map, geojson_og, geobuf = setup_data(directory)

colorscale = ['#3f2bff', '#5b9efc', '#8DEACE', '#F4A38A', '#FB6161', '#00aeff', '#57bfff',
              '#00ff15', '#FF5CB0', '#bdff63', '#388ccf', '#21adb8', '#ff2e7e', '#2967A5', '#20AB8B', '#f7e38b',
              '#4566D6', '#71B8AC', '#FF44FC', '#93FF3B', '#33CBFF', '#FF6126', '#9078AC', '#8a9aff', '#861dc2',
              '#DBFF35', '#7433FF', '#C3C2C2', '#F9BF19', '#57d63a', '#B571EB', '#e8cf07', '#68cbed', '#CE4E99',
              '#9e334b', '#E770FF', '#787878', '#41e060', '#33FEE7', '#47b541', '#08bd6a', '#099c58', '#a7c3fa',
              '#f5ee14', '#5438c7', '#D13BD9', '#e87743', '#94d6d6', '#33E4FF', '#8944FE', '#29e3a3', '#575757',
              '#faad4d', '#a0cf34', '#CC44FD', '#e06019', '#33FE8A', '#FFFFFF']

# can change seed until you like the color assignment
random.seed(49)
random.shuffle(colorscale)

chroma = "https://cdnjs.cloudflare.com/ajax/libs/chroma-js/2.1.0/chroma.min.js"  # js lib used for colors
color_prop = 'category'

def colorbar_and_gj(df, uniques):
    vmax = df[color_prop].max()
    ctg = list(uniques)

    # Create geojson
    ns = Namespace("dashExtensions", "default")  # points to dashExtensions_default.js
    gj = dl.GeoJSON(data=geojson_og, id="geojson_l",
                        zoomToBounds=False,  # when true, zooms to bounds when data changes
                        options=dict(pointToLayer=ns('function0')),  # how to draw points
                        superClusterOptions=dict(radius=50),   # adjust cluster size
                        hideout=dict(colorProp=color_prop, circleOptions=dict(fillOpacity=1, stroke=False, radius=7),
                                    strokeColor='white', min=0, max=vmax, colorscale=colorscale,
                                    selected=[]))
    return ctg, gj

ctg, gj = colorbar_and_gj(zip_df, uniques)

#################################################################################
#starting point for tables
tbl_df = totalstable('TerritoryName', df)  # doesn't change
zip_tbl = pd.DataFrame(columns=['ProducerName', 'OpptyType', 'TotalAssets'])  # empty table with column names

app = Dash(__name__, external_scripts=[chroma], prevent_initial_callbacks=True, compress=False, assets_folder='assets')
app.title = "Total Assets by Territory"
cache = Cache(app.server, config={
    # try 'filesystem' if you don't want to setup redis
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': '/tmp'
})
app.config.suppress_callback_exceptions = True
server = app.server
TIMEOUT = 60

app.layout = html.Div([
    dcc.Dropdown(ctg, value=[], placeholder='Select territories to examine', multi=True, id='en_select',
                 )
    ,html.Div([
        # map
        html.Div(dl.Map(
            [
                dl.TileLayer(),
                gj,
                dl.FeatureGroup([dl.EditControl(id="edit_control", position='topright')])
            ],
            style={'height': '65vh', 'width': '100%'},  # requires explicit hw but let parent define width
            center=[40,-90], zoom=4.5, id="map",
        ), style={'display': 'inline-block', 'verticalAlign': 'top', 'marginTop': '2vh', 'marginBottom': '2vh',
                  'width': '68%', 'height': '65vh'}
        ),
        html.Div([
            html.Div(children='Zipcode Specifics',
                     style={'color': 'black', 'fontSize': 20, 'verticalAlign': 'top', 'marginBottom': '1vh'}, id='ziptext'
                     ),
            html.Div(dash_table.DataTable(data=None, columns=[{"name": i, "id": i} for i in zip_tbl.columns], id='zipcodetbl'
                                          ),
                     style={'marginTop': '1vh', 'maxHeight': '61.5vh', 'overflowY': 'auto'}
                     )
        ],
            style={'width': '27%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginTop': '2vh', 'marginLeft': '2vh'
                   }
        )],
        style={'whiteSpace': 'nowrap'}  # removes inline spacing
    )
    ,dcc.Dropdown(ctg, value=None, id='editing-dropdown', placeholder='Select territory to edit')
    ,dash_table.DataTable(data=tbl_df.to_dict('records'), columns =[{"name": i, "id": i} for i in tbl_df.columns], id='territorytbl')
    ,html.Button('Download Territory Allocations', id='btn_csv_1')
    ,dcc.Download(id='download-territory-csv')
])

############# SELECT ZIPCODE FOR DETAILS #############

@app.callback(
    Output('ziptext', 'children'),
    Output('zipcodetbl', 'data'),
    Output('geojson_l', 'hideout'),
    Input('geojson_l', 'n_clicks'),
    State('geojson_l', 'clickData'),  # changed from click_feature
    State('geojson_l', 'hideout'),
    prevent_initial_call=True
)

def toggle_select(_, feature, hideout):
    """Highlights (or unhighlights) clicked zipcode and shows side table

    Args:
        n_clicks: integer property = cumulative no. of clicks. needed in callback to update interface to respond to every zipcode click
        feature: (click_feature) retrieves data from feature (zipcode) that was clicked
        hideout: contains a list, 'selected', that remembers highlighted zipcode. 'selected' is also used in dashExtensions_default.js for outlining the point

    Returns:
        ziptext (children): dynamic title of side zipcode table
        zipcodetbl (data): data rows of side zipcode table, i.e. rows of the zipcode grouped by producer name and oppty type, showing total oppty value
        geojson_l (hideout): property that can tell geojson how to display content
    """
    if feature:
        zipcode = feature['properties']['PostalCode']
        selected = hideout['selected']
        # if same zipcode is clicked twice in a row, deselect it
        if zipcode in selected:
            hideout['selected'] = []
            ziptbl = None
            text = 'Zipcode Specifics'
        else:
            hideout['selected'] = [zipcode]
            ziptbl = df[df['PostalCode']==zipcode][['ProducerName', 'OpptyType', 'TotalAssets']]
            ziptbl = ziptbl.groupby(['ProducerName', 'OpptyType']).sum().reset_index().to_dict('records')
            text = f'Zipcode Specifics: {zipcode}'
        return text, ziptbl, hideout
    else:
        return no_update, no_update, no_update

############# ALL IN ONE -__- ##################

@app.callback(
    Output('geojson_l', 'data'),
    Output('territorytbl', 'data'),
    Output('edit_control', 'editToolbar'),
    Output('editing-dropdown', 'options'),
    Input('en_select', 'value'),
    Input('edit_control', 'geojson'),
    State('editing-dropdown', 'value'),
    )
@cache.memoize(timeout=TIMEOUT)

def everything_everywhere(selected_territories, edit_control, editing_territory):
    changed_inputs = [
        x["prop_id"]
        for x in callback_context.triggered
    ]
    print("changed_inputs are:", changed_inputs, "\n")

    res = df  # have to read from long format df every time, since data (tbl_df) is wide format
    coords = find_geo(edit_control)

    # if editing territory is removed from selected territories, set to None. or else its ghost lingers
    if editing_territory not in selected_territories:
        editing_territory = None

    if (not edit_control['features'] and selected_territories):
        print('cond 1: no edit controls and selected territories')

        df_ = res[res['TerritoryName'].isin(selected_territories)].copy()  
        df_.iscopy = False

        tbl_df_ = totalstable('TerritoryName', df_)
        zip_df_ = update_zip(df_)

        dicts = hoverdict(zip_df_)
        geojson = dlx.dicts_to_geojson(dicts, lon="Longitude", lat="Latitude")  # convert to geojson

        return geojson, tbl_df_.to_dict('records'), no_update, selected_territories

    if selected_territories and coords and editing_territory:
        print('cond 2: selected territories, coords, editing territory')
        # do all three; change whats selected, then compute intersection
        # edit df to reflect selection

        df_ = res[res['TerritoryName'].isin(selected_territories)].copy()
        print(len(df[df['TerritoryName'] == editing_territory]))
        df_.iscopy = False

        # now compute intersection
        bounding_boxes = [Polygon(x[0]) for x in coords]
        gpd_ = gp.GeoDataFrame(df_, geometry =gp.points_from_xy(df_.Longitude,df_.Latitude))
        intersections = []
        for bounding_box in bounding_boxes:
            intersection = gpd_.intersects(gp.GeoSeries(bounding_box).unary_union)
            intersections.append(intersection)
        intersection = np.array(intersections).any(0)
        df_.loc[intersection,'TerritoryName'] = editing_territory
        df_.loc[intersection,'category'] = cat_terr_map[editing_territory]
        #now compute the resulting table by groupby stuff
        tbl_df_ = totalstable('TerritoryName', df_)
        zip_df_ = update_zip(df_)

        #convert resulant geojson to geojson
        dicts = hoverdict(zip_df_)
        geojson = dlx.dicts_to_geojson(dicts, lon="Longitude", lat="Latitude")  # convert to geojson

        return geojson, tbl_df_.to_dict('records'), no_update, selected_territories

    if (selected_territories and not coords) or (selected_territories and not editing_territory):
        print('part 2')
        # selected territories but either there is a poly and no specified new terr, or there is a specified new terr and no poly, so we will simply update table and plot to reflect this 
        df_ = res[res['TerritoryName'].isin(selected_territories)].copy()
        df_.iscopy = False

        tbl_df_ = totalstable('TerritoryName', df_)
        zip_df_ = update_zip(df_)

        dicts = hoverdict(zip_df_)
        geojson = dlx.dicts_to_geojson(dicts, lon="Longitude", lat="Latitude")  # convert to geojson

        return geojson, tbl_df_.to_dict('records'), no_update, selected_territories

    else:
        print("\n Nothing selected... i.e., no territories, no shapes...\n")
        # nothing selected so return original geojson and clear any drawings
        if 'en_select.value' in changed_inputs:  # if territories are cleared, clear shapes and editing territory
            return geojson_og, tbl_df.to_dict('records'), dict(mode="remove", action="clear all"), []
        else:
            return geojson_og, tbl_df.to_dict('records'), no_update, []

@app.callback(
    Output('download-territory-csv', 'data'),
    Input('btn_csv_1', 'n_clicks'),
    State('geojson_l', 'data'),
    prevent_inital_callback=True,
)

def gen_terri_output(n_clicks,data):
    props = []
    for v in data['features']:
        props.append(v['properties'])
        res = pd.DataFrame(props)
        res = res.iloc[:, 0:8]   # omit category, tooltip, cluster columns
    return dcc.send_data_frame(res.to_csv, 'output_territories.csv', index=False)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=None)
