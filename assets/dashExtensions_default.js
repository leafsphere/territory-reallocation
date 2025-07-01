window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, latlng, context) {
            console.log(feature);
            console.log(context);
            const {
                min,
                max,
                colorscale,
                circleOptions,
                colorProp,
                selected
            } = context.hideout; // changed from context.props.hideout
            const csc = chroma.scale(colorscale).domain([min, max]); // chroma lib to construct colorscale
            circleOptions.fillColor = csc(feature.properties[colorProp]); // set color based on color prop.
            if (selected.includes(feature.properties.PostalCode)) {
                circleOptions.stroke = true;
                circleOptions.color = 'black';
                circleOptions.weight = 5;
            } else {
                circleOptions.stroke = false;
            }
            console.log(circleOptions);
            return L.circleMarker(latlng, circleOptions); // sender a simple circle marker.
        }

    }
});