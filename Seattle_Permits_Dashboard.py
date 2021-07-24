import dash  # pip install dash==1.21.0
import dash_bootstrap_components as dbc  # pip install dash_bootstrap_components==0.12.2
import dash_core_components as dcc  # pip install dash_core_components==1.17.1
import dash_html_components as html  # pip install dash_html_components==1.1.4
import pandas as pd  # pip install pandas==1.2.3
import plotly.express as px  # pip install plotly==5.1.0
import plotly.graph_objects as go
from dash.dependencies import Input, Output
import gunicorn  # pip install gunicorn==20.1.0

df = (pd.read_csv('Building_Permit_Map.csv'))

not_active = ['Completed', 'Closed', 'Expired', 'Canceled', 'Withdrawn']
df_active = df[~df['StatusCurrent'].isin(not_active)]

permit_class_remap = {'Commercial': 'Non-Residential',
                      'Institutional': 'Non-Residential',
                      'Industrial': 'Non-Residential',
                      'Vacant Land': 'Non-Residential'}
df_active['PermitClassMapRes'] = (df_active['PermitClass']
                                  .replace(permit_class_remap))

df_active = df_active[~df_active['OriginalZip'].isna()]
df_active['OriginalZip'] = df_active['OriginalZip'].astype(int)
df_has_loc = df_active[~df_active['Latitude'].isna()]
df_has_loc = df_has_loc[df_has_loc.OriginalZip != 0]

# Fill null values
df_has_loc['EstProjectCost'].fillna('Unknown', inplace=True)
df_has_loc['HousingUnitsAdded'].fillna(0, inplace=True)
df_has_loc['HousingUnitsRemoved'].fillna(0, inplace=True)

# Remove unneeded columns
cols = ['PermitNum', 'PermitClassMapRes', 'PermitTypeDesc',
        'HousingUnitsRemoved', 'HousingUnitsAdded', 'OriginalZip',
        'Longitude', 'Latitude', 'EstProjectCost', 'PermitClassMapped']
df_has_loc = df_has_loc[cols]

# Filter to just Additions, New, and Demo permits
df_has_loc = df_has_loc[df_has_loc['PermitTypeDesc'].isin(
                                ['Addition/Alteration', 'New', 'Demolition'])]
# Check final nulls
df_has_loc.isna().sum()

# Remove 22 rows with missing class
df_has_loc = df_has_loc.dropna()

# Convert zips to strings
df_has_loc = df_has_loc.astype(dtype={'OriginalZip': 'str'})

# Make list of unique zips
unique_zips = df_has_loc['OriginalZip'].drop_duplicates().sort_values().tolist()

# Group and count permit types per Zip for charts
type_grouper = (df_has_loc.groupby(['OriginalZip',
                                   'PermitTypeDesc', 'PermitClassMapRes'])['PermitNum']
                .count().reset_index())
type_mapper = {'PermitNum': 'PermitTypeCount',
               'PermitClassMapRes': 'PermitClass'}
type_grouper = type_grouper.rename(mapper=type_mapper, axis='columns')

# Group and count permit type per Zip
zip_type_g = (df_has_loc.groupby(['OriginalZip',
                                  'PermitTypeDesc'])['PermitNum']
              .count().reset_index())
zip_type_g = zip_type_g.rename(mapper={'PermitNum': 'PermitTypeCount'},
                               axis='columns')

# Count total type permits per zip
zip_t_g = zip_type_g.groupby('OriginalZip')['PermitTypeCount'].sum().reset_index()
zip_t_g = zip_t_g.rename(mapper={'PermitTypeCount': 'TotalTypePermit'},
                         axis='columns')

zip_type_g = zip_type_g.merge(zip_t_g, how='left', on='OriginalZip')

# calc percent of each type permit per zip
zip_type_g['pct_permit_type'] = round((zip_type_g['PermitTypeCount']
                                      / zip_type_g['TotalTypePermit']), 4)

# Group and count permit type per Zip
zip_class_g = (df_has_loc.groupby(['OriginalZip',
                                   'PermitClassMapRes'])['PermitNum']
               .count().reset_index())
zip_class_g = zip_class_g.rename(mapper={'PermitNum': 'PermitClassCount'},
                                 axis='columns')

# Count total class permits per zip and merge
zip_c_g = (zip_class_g.groupby('OriginalZip')['PermitClassCount']
           .sum().reset_index())
zip_c_g = zip_c_g.rename(mapper={'PermitClassCount': 'TotalClassPermit'},
                         axis='columns')
zip_class_g = zip_class_g.merge(zip_c_g, how='left', on='OriginalZip')

# calc percent of each class permit per zip
zip_class_g['pct_permit_class'] = round((zip_class_g['PermitClassCount']
                                         / zip_class_g['TotalClassPermit']), 4)

# Dash app layout
bg_color = '#f0f8ff'
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
server = app.server

app.layout = dbc.Container([
    dbc.Row(
        dbc.Col(
            html.H1("Active Construction Permits in Seattle"),
            style={'text-align': 'center'}), style={'margin-bottom': 25}
            ),
    dbc.Row(
        [dbc.Col(dcc.Slider(id="type_or_class", min=0,
                            max=1,
                            step=1,
                            marks=
                            {0: "Class",
                             1: "Type"},
                            value=0),
                 width={'size': 4, 'offset': 0, 'order': 1}
                 ),
         dbc.Col(dcc.Slider(id="pct_or_total", min=0,
                            max=1,
                            step=1,
                            marks=
                            {0: "Percent",
                             1: "Total"},
                            value=0),
                 width={'size': 4, 'offset': 2, 'order': 2})]),
    dbc.Row([
        dbc.Col([dcc.Dropdown(id="slct_zip",
                              options=[{'label': zip,
                                       'value': zip} for zip in unique_zips
                                       ], multi=True,
                              value=[],
                              placeholder='Select Zip Codes, All by Default'),
                dcc.Graph(id='sea_permit_map', figure={})],
                width=4),
        dbc.Col([  # second columns for graphs
                dcc.Graph(id='horizontal_bar_type', figure={}),
                dcc.Graph(id='horizontal_bar_class', figure={}),
                ], width=8),
        ]),
    dbc.Row(
        dbc.Col(
            html.H5("Datasource: https://data.seattle.gov/"),
            style={'text-align': 'left'})
            ),
    dbc.Row(
        dbc.Col(
            html.H5("Dashboard by Clayton Brock"),
            style={'text-align': 'left'})
            ),
], fluid=True, style={'backgroundColor': bg_color})


# In[19]:


@app.callback(
    [Output(component_id='sea_permit_map', component_property='figure'),
     Output(component_id='horizontal_bar_class', component_property='figure'),
     Output(component_id='horizontal_bar_type', component_property='figure')],
    [Input(component_id='type_or_class', component_property='value'),
     Input(component_id='slct_zip', component_property='value'),
     Input(component_id='pct_or_total', component_property='value')]
)
def update_map(type_class, slct_zip, pct_total):

    df1 = df_has_loc.copy()
    # df2 = type_grouper.copy()  # for filtering on type and class
    df3 = zip_type_g.copy()
    df4 = zip_class_g.copy()

# -------MAP---------------------------
    if bool(slct_zip) is False:
        print('no zip')
    else:
        df1 = df1[df1['OriginalZip'].isin(slct_zip)]

    if type_class == 0:   # Color map by class
        fig_map = px.scatter_mapbox(
                df1,
                lon='Longitude',
                lat='Latitude',
                labels={'PermitTypeDesc': 'Permit Type',
                        'PermitNum': 'Permit Number',
                        'OriginalZip': 'Zip Code',
                        'PermitClassMapRes': 'Permit Class'
                        },
                hover_data={'Longitude': False,
                            'Latitude': False,
                            'OriginalZip': True,
                            'PermitNum': True,
                            'PermitTypeDesc': True,
                            'PermitClassMapRes': True},
                mapbox_style='open-street-map',
                color='PermitClassMapRes',
                color_discrete_map={"Single Family/Duplex": '#e9a3c9',
                                    'Multifamily': '#c51b7d',
                                    'Non-Residential': '#4d9221'},
                zoom=10,
                height=800,
                width=700)
    elif type_class == 1:   # Color map by type
        fig_map = px.scatter_mapbox(
                df1,
                lon='Longitude',
                lat='Latitude',
                hover_data={'Longitude': False,
                            'Latitude': False,
                            'OriginalZip': True,
                            'PermitNum': True,
                            'PermitTypeDesc': True,
                            'PermitClassMapRes': True},
                mapbox_style='open-street-map',
                color='PermitTypeDesc',
                labels={'PermitTypeDesc': 'Permit Type',
                        'PermitNum': 'Permit Number',
                        'OriginalZip': 'Zip Code',
                        'PermitClassMapRes': 'Permit Class'
                        },
                color_discrete_map={"New": '#2166ac',
                                    'Demolition': '#b2182b',
                                    'Addition/Alteration': '#67a9cf'},
                zoom=10,
                height=800,
                width=700)

    fig_map.update_traces(marker=dict(size=4))
    fig_map.update_layout(showlegend=True,
                          legend={'orientation': "h",
                                  'yanchor': "bottom",
                                  'y': 1.02,
                                  'xanchor': "right",
                                  'x': 1,
                                  'title': '',
                                  'itemsizing': 'constant',
                                  'itemwidth': 30},
                          paper_bgcolor=bg_color)

# ------------------CLASS BAR CHART___________________

    if pct_total == 1:  # TOTAL TOTAL
        if bool(slct_zip) is False:
            fig_class = px.bar(df4, x="PermitClassCount", y="OriginalZip",
                               color='PermitClassMapRes', orientation='h',
                               labels={'PermitClassCount': 'Zip Class Total',
                                       'TotalClassPermit': 'Zip Permit Total',
                                       'OriginalZip': 'Zip Code',
                                       'PermitClassMapRes': 'Permit Class',
                                       'pct_permit_class': 'Zip Class Percent'
                                       },
                               hover_data=['PermitClassMapRes',
                                           'PermitClassCount',
                                           'TotalClassPermit',
                                           'pct_permit_class'],
                               height=400,
                               title='Total of Each Permit Class Per Zip Code',
                               color_discrete_map={
                                    "Single Family/Duplex": '#e9a3c9',
                                    'Multifamily': '#c51b7d',
                                    'Non-Residential': '#4d9221'}
                               )
            fig_class.update_yaxes({'showticklabels': False,
                                    'title': {'text': 'Zip Code'}})
            fig_class.update_xaxes({'showticklabels': True,
                                    'title': {'text': ''}})

        else:
            df4 = df4[df4['OriginalZip'].isin(slct_zip)]
            fig_class = px.bar(df4, x="PermitClassCount", y="OriginalZip",
                               color='PermitClassMapRes', orientation='h',
                               labels={'PermitClassCount': 'Zip Class Total',
                                       'TotalClassPermit': 'Zip Permit Total',
                                       'OriginalZip': 'Zip Code',
                                       'PermitClassMapRes': 'Permit Class',
                                       'pct_permit_class': 'Zip Class Percent'
                                       },
                               hover_data=['PermitClassMapRes',
                                           'PermitClassCount',
                                           'TotalClassPermit',
                                           'pct_permit_class'],
                               height=400,
                               title='Total of Each Permit Class Per Zip Code',
                               color_discrete_map={
                                    "Single Family/Duplex": '#e9a3c9',
                                    'Multifamily': '#c51b7d',
                                    'Non-Residential': '#4d9221'}
                               )
            fig_class.update_yaxes({'showticklabels': True,
                                    'title': {'text': 'Zip Code'}})
            fig_class.update_xaxes({'showticklabels': True,
                                    'title': {'text': ''}})

    elif pct_total == 0:  # PERCENT
        if bool(slct_zip) is False:
            fig_class = px.bar(df4, x="pct_permit_class", y="OriginalZip",
                               color='PermitClassMapRes', orientation='h',
                               labels={'PermitClassCount': 'Zip Class Total',
                                       'TotalClassPermit': 'Zip Permit Total',
                                       'OriginalZip': 'Zip Code',
                                       'PermitClassMapRes': 'Permit Class',
                                       'pct_permit_class': 'Zip Class Percent'
                                       },
                               hover_data=["PermitClassMapRes",
                                           "PermitClassCount",
                                           'TotalClassPermit'],
                               height=400,
                               title='Percent of Each Permit Class Per Zip Code',
                               color_discrete_map={
                                    "Single Family/Duplex": '#e9a3c9',
                                    'Multifamily': '#c51b7d',
                                    'Non-Residential': '#4d9221'}
                               )
            fig_class.update_yaxes({'showticklabels': False,
                                    'title': {'text': 'Zip Code'}})
            fig_class.update_xaxes({'showticklabels': True,
                                    'title': {'text': ''},
                                    'tickformat': '%'})

        else:
            df4 = df4[df4['OriginalZip'].isin(slct_zip)]
            fig_class = px.bar(df4, x="pct_permit_class", y="OriginalZip",
                               color='PermitClassMapRes', orientation='h',
                               labels={'PermitClassCount': 'Zip Class Total',
                                       'TotalClassPermit': 'Zip Permit Total',
                                       'OriginalZip': 'Zip Code',
                                       'PermitClassMapRes': 'Permit Class',
                                       'pct_permit_class': 'Zip Class Percent'
                                       },
                               hover_data=["PermitClassMapRes",
                                           "PermitClassCount",
                                           'TotalClassPermit'],
                               height=400,
                               title='Percent of Each Permit Class Per Zip Code',
                               color_discrete_map={
                                    "Single Family/Duplex": '#e9a3c9',
                                    'Multifamily': '#c51b7d',
                                    'Non-Residential': '#4d9221'}
                               )
            fig_class.update_yaxes({'showticklabels': True,
                                    'title': {'text': 'Zip Code'}})
            fig_class.update_xaxes({'showticklabels': True,
                                    'title': {'text': ''},
                                    'tickformat': '%'})
    fig_class.update_layout(legend={
                                        'orientation': "h",
                                        'yanchor': "bottom",
                                        'y': 1.02,
                                        'xanchor': "left",
                                        'x': 0,
                                        'title': ''
                                            },
                            paper_bgcolor=bg_color
                            )

# -----------------TYPE BAR CHART-------------------

    if pct_total == 1:     # TOTAL
        if bool(slct_zip) is False:
            fig_type = px.bar(df3, x="PermitTypeCount", y="OriginalZip",
                              color='PermitTypeDesc', orientation='h',
                              labels={'PermitTypeDesc': 'Permit Type',
                                      'TotalTypePermit': 'Zip Permit Total',
                                      'OriginalZip': 'Zip Code',
                                      'PermitTypeCount': 'Zip Type Total',
                                      'pct_permit_type': 'Zip Type Percent'
                                      },
                              hover_data=["PermitTypeDesc", "PermitTypeCount",
                                          'TotalTypePermit'],
                              height=400,
                              title='Total of Each Permit Type Per Zip Code',
                              color_discrete_map={"New": '#2166ac',
                                                  'Demolition': '#b2182b',
                                                  'Addition/Alteration':
                                                  '#67a9cf'})
            fig_type.update_yaxes({'showticklabels': False,
                                   'title': {'text': 'Zip Code'}})
            fig_type.update_xaxes({'showticklabels': True,
                                   'title': {'text': ''}})

        else:
            df3 = df3[df3['OriginalZip'].isin(slct_zip)]
            fig_type = px.bar(df3, x="PermitTypeCount", y="OriginalZip",
                              color='PermitTypeDesc', orientation='h',
                              labels={'PermitTypeDesc': 'Permit Type',
                                      'TotalTypePermit': 'Zip Permit Total',
                                      'OriginalZip': 'Zip Code',
                                      'PermitTypeCount': 'Zip Type Total',
                                      'pct_permit_type': 'Zip Type Percent'
                                      },
                              hover_data=["PermitTypeDesc", "PermitTypeCount",
                                          'TotalTypePermit'],
                              height=400,
                              title='Total of Each Permit Type Per Zip Code',
                              color_discrete_map={"New": '#2166ac',
                                                  'Demolition': '#b2182b',
                                                  'Addition/Alteration':
                                                  '#67a9cf'})
            fig_type.update_yaxes({'showticklabels': True,
                                   'title': {'text': 'Zip Code'}})
            fig_type.update_xaxes({'showticklabels': True,
                                   'title': {'text': ''}})

    if pct_total == 0:     # PERCENT PERCENT
        if bool(slct_zip) is False:
            fig_type = px.bar(df3, x="pct_permit_type", y="OriginalZip",
                              color='PermitTypeDesc', orientation='h',
                              labels={'PermitTypeDesc': 'Permit Type',
                                      'TotalTypePermit': 'Zip Permit Total',
                                      'OriginalZip': 'Zip Code',
                                      'PermitTypeCount': 'Zip Type Total',
                                      'pct_permit_type': 'Zip Type Percent'
                                      },
                              hover_data=["PermitTypeDesc", "PermitTypeCount",
                                          'TotalTypePermit'],
                              height=400,
                              title='Percent of Each Permit Type Per Zip Code',
                              color_discrete_map={"New": '#2166ac',
                                                  'Demolition': '#b2182b',
                                                  'Addition/Alteration':
                                                  '#67a9cf'})
            fig_type.update_yaxes({'showticklabels': False,
                                   'title': {'text': 'Zip Code'}})
            fig_type.update_xaxes({'showticklabels': True,
                                   'title': {'text': ''},
                                   'tickformat': '%'})

        else:
            df3 = df3[df3['OriginalZip'].isin(slct_zip)]
            fig_type = px.bar(df3, x="pct_permit_type", y="OriginalZip",
                              color='PermitTypeDesc', orientation='h',
                              labels={'PermitTypeDesc': 'Permit Type',
                                      'TotalTypePermit': 'Zip Permit Total',
                                      'OriginalZip': 'Zip Code',
                                      'PermitTypeCount': 'Zip Type Total',
                                      'pct_permit_type': 'Zip Type Percent'
                                      },
                              hover_data=["PermitTypeDesc", "PermitTypeCount",
                                          'TotalTypePermit'],
                              height=400,
                              title='Percent of Each Permit Type Per Zip Code',
                              color_discrete_map={"New": '#2166ac',
                                                  'Demolition': '#b2182b',
                                                  'Addition/Alteration':
                                                  '#67a9cf'})
            fig_type.update_yaxes({'showticklabels': True,
                                   'title': {'text': 'Zip Code'}})
            fig_type.update_xaxes({'showticklabels': True,
                                   'title': {'text': ''},
                                   'tickformat': '%'})
    fig_type.update_layout(legend={
                                'orientation': "h",
                                'yanchor': "bottom",
                                'y': 1.02,
                                'xanchor': "left",
                                'x': 0,
                                'title': ''
                                    },
                           paper_bgcolor=bg_color
                           )

    return (fig_map, fig_class, fig_type)


if __name__ == '__main__':
    app.run_server(debug=True)
